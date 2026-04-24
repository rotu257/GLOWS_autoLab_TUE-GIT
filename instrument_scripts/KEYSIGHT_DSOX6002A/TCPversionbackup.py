#!/home/user_rotu/GLOWS_autoLab_python3_venv/bin/python


"""
Acquire waveforms from Keysight/Agilent InfiniiVision 6000 X-Series over LAN.

Includes:
- Correct 10-field :WAV:PRE? mapping:
  FORMAT, TYPE, POINTS, COUNT, XINC, XORIG, XREF, YINC, YORIG, YREF
- Tight logging (points, transfer limits, bytes/pt, scaling params)
- RAW points mode + requests MAX transfer points
- Chunked download via :WAV:STAR/:WAV:STOP (binary) to fetch full record
- NEW: --plot flag (plots scaled data after acquisition)

Notes:
- Plotting uses matplotlib. Install: pip install matplotlib
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pyvisa
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

DEFAULT_RESOURCE = "TCPIP0::192.168.1.14::INSTR"

MAX_POINTS_HALF_CHANNEL = 4_000_000
MAX_POINTS_FULL_CHANNEL = 2_000_000


class OscilloscopeConfig(BaseModel):
    channels: List[str] = Field(default=["CHAN1"])
    resource: str = Field(default=DEFAULT_RESOURCE)
    filename: Optional[str] = Field(default=None)
    force: bool = Field(default=False)
    timeout: float = Field(default=40.0, gt=0)
    autoset: bool = Field(default=False)
    ascii: bool = Field(default=False)
    max_points: bool = Field(default=True)
    csv: bool = Field(default=False, description="Also save scaled CSV (time_s,voltage_V)")
    chunk_points: int = Field(default=250_000, gt=0, description="Chunk size for binary transfers")
    plot: bool = Field(default=False, description="Plot scaled data after acquisition")
    plot_max_points: int = Field(default=300_000, gt=1000, description="Max points to draw per channel")

    def save_to_file(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)
        logger.info(f"Config saved → {path}")

    @classmethod
    def load_from_file(cls, path: str) -> "OscilloscopeConfig":
        with open(path, "r") as f:
            data = json.load(f)
        return cls(**data)


class KeysightInfiniiVision6000X:
    def __init__(self, config: OscilloscopeConfig):
        self.config = config
        self.rm = pyvisa.ResourceManager("@py")
        self.scope = None
        self._connect()
        self._validate_channels()

    def _connect(self) -> None:
        self.scope = self.rm.open_resource(self.config.resource)
        self.scope.timeout = int(self.config.timeout * 1000)
        self.scope.read_termination = "\n"
        self.scope.write_termination = "\n"
        self.scope.chunk_size = 32768

        idn = self.query("*IDN?").strip()
        logger.info(f"Connected via LAN: {idn}")

    def _validate_channels(self) -> None:
        valid = [f"CHAN{i}" for i in range(1, 5)]
        for ch in self.config.channels:
            if ch not in valid:
                raise ValueError(f"Invalid channel: {ch}")
        logger.info(f"Channels: {', '.join(self.config.channels)}")

    def query(self, cmd: str) -> str:
        return self.scope.query(cmd).strip()

    def write(self, cmd: str) -> None:
        self.scope.write(cmd)

    def _wait_opc(self, timeout_sec: float = 180.0) -> None:
        start = time.time()
        while time.time() - start < timeout_sec:
            if self.query("*OPC?") == "1":
                return
            time.sleep(0.3)
        logger.warning(f"OPC timeout after {timeout_sec:.1f} s — continuing anyway")

    def reset(self) -> None:
        logger.info("Resetting instrument (*RST)...")
        self.write("*RST")
        self._wait_opc()

    def autoset(self) -> None:
        logger.info("Running :AUToscale...")
        self.write(":AUToscale")
        self._wait_opc()

    def set_max_record_length(self) -> None:
        if not self.config.max_points:
            return
        n_ch = len(self.config.channels)
        target = MAX_POINTS_HALF_CHANNEL if n_ch <= 2 else MAX_POINTS_FULL_CHANNEL
        try:
            self.write(":ACQuire:POINts:AUTO OFF")
            self.write(f":ACQuire:POINts {target}")
            actual = int(float(self.query(":ACQuire:POINts?")))
            logger.info(f"Record length set → {actual:,} points (requested {target:,})")
        except Exception as e:
            logger.warning(f"Could not set max points: {e} — using instrument default")

    def configure_waveform_format(self) -> None:
        fmt = "ASCii" if self.config.ascii else "BYTE"
        self.write(f":WAVeform:FORMat {fmt}")
        self.write(":WAVeform:BYTorder LSBFirst")
        self.write(":WAVeform:POINts:MODE RAW")

        if not self.config.ascii:
            try:
                self.write(":WAVeform:UNSigned 1")
            except Exception:
                pass

        logger.info(f"Waveform format: {fmt} (RAW points mode)")
        if self.config.ascii:
            logger.warning("ASCII format selected — slow and often limited; prefer binary.")

    def _set_transfer_points_max(self, ch: str) -> int:
        self.write(f":WAVeform:SOURce {ch}")
        self.write(":WAVeform:POINts:MODE RAW")
        try:
            self.write(":WAVeform:POINts MAX")
        except Exception:
            pass
        return int(float(self.query(":WAVeform:POINts?")))

    def get_preamble_dict(self, ch: str) -> Dict:
        """
        Keysight/Agilent 10-field preamble:
        FORMAT, TYPE, POINTS, COUNT, XINC, XORIG, XREF, YINC, YORIG, YREF
        """
        self.write(f":WAVeform:SOURce {ch}")
        raw = self.query(":WAVeform:PREamble?")
        vals = [float(x) for x in raw.split(",")]
        if len(vals) < 10:
            raise ValueError(f"Unexpected preamble length={len(vals)}: {raw}")

        return {
            "format": int(vals[0]),
            "type": int(vals[1]),
            "points": int(vals[2]),
            "count": int(vals[3]),
            "xincrement": vals[4],
            "xorigin": vals[5],
            "xreference": int(vals[6]),
            "yincrement": vals[7],
            "yorigin": vals[8],
            "yreference": int(vals[9]),
            "raw": raw,
        }

    def _read_block_data(self) -> bytes:
        header = self.scope.read_bytes(2).decode("ascii", errors="ignore")
        if not header.startswith("#"):
            raise ValueError(f"Unexpected block header: {header!r}")
        length_digits = int(header[1])
        length_str = self.scope.read_bytes(length_digits).decode("ascii")
        data_length = int(length_str)
        raw_data = self.scope.read_bytes(data_length)
        self.scope.read_bytes(1)  # trailing newline
        return raw_data

    def _query_waveform_block(self) -> bytes:
        self.scope.write(":WAVeform:DATA?")
        return self._read_block_data()

    def _decode_binary_values(self, raw_data: bytes, preamble: Dict) -> np.ndarray:
        fmt = int(preamble["format"])
        if fmt == 0:
            return np.frombuffer(raw_data, dtype=np.uint8)
        if fmt == 1:
            return np.frombuffer(raw_data, dtype="<i2")
        raise ValueError(f"Unsupported preamble format={fmt}")

    @staticmethod
    def _expected_bytes_per_point(preamble: Dict) -> int:
        fmt = int(preamble["format"])
        return 1 if fmt == 0 else 2 if fmt == 1 else 1

    def _log_waveform_summary(self, ch: str, preamble: Dict, raw_len: int, transfer_pts: int) -> None:
        pts = int(preamble["points"])
        fmt = int(preamble["format"])
        bpp = self._expected_bytes_per_point(preamble)
        expected_bytes = transfer_pts * bpp if transfer_pts else None

        logger.info(
            f"{ch} preamble: fmt={fmt} type={preamble['type']} pts(acq)={pts:,} cnt={preamble['count']} "
            f"xinc={preamble['xincrement']:.3e} xorg={preamble['xorigin']:.3e} xref={preamble['xreference']} "
            f"yinc={preamble['yincrement']:.3e} yorg={preamble['yorigin']:.6g} yref={preamble['yreference']} "
            f"| transfer_pts={transfer_pts:,} raw_bytes={raw_len:,}"
            + (f" expected_bytes≈{expected_bytes:,}" if expected_bytes is not None else "")
        )

        if pts and transfer_pts and transfer_pts < pts:
            logger.warning(
                f"{ch} transfer is limited ({transfer_pts:,} pts) vs acquisition ({pts:,} pts). "
                f"Chunking will be used to fetch the full record."
            )

        if transfer_pts:
            ratio = raw_len / max(1, transfer_pts)
            logger.info(f"{ch} bytes/point ≈ {ratio:.3f} (expect ~{bpp:.1f} for this format)")

    @staticmethod
    def _scaled_times_for_chunk(preamble: Dict, start_1based: int, n: int) -> np.ndarray:
        xinc = float(preamble["xincrement"])
        xorg = float(preamble["xorigin"])
        xref = float(preamble["xreference"])
        idx0 = start_1based - 1
        return (np.arange(n, dtype=np.float64) + idx0 - xref) * xinc + xorg

    @staticmethod
    def _scaled_volts(values: np.ndarray, preamble: Dict) -> np.ndarray:
        yinc = float(preamble["yincrement"])
        yorg = float(preamble["yorigin"])
        yref = float(preamble["yreference"])
        return (values.astype(np.float64) - yref) * yinc + yorg

    def download_waveform_scaled(self, ch: str) -> Tuple[np.ndarray, np.ndarray, bytes, Dict, int]:
        self.write(f":WAVeform:SOURce {ch}")
        transfer_pts_max = self._set_transfer_points_max(ch)
        preamble = self.get_preamble_dict(ch)
        acq_pts = int(preamble["points"])

        if self.config.ascii:
            raw = self._query_waveform_block()
            # NOTE: ASCII parsing is simplistic; recommend binary.
            text = raw.decode("utf-8", errors="ignore").strip()
            if text.startswith("#"):
                i = 2
                while i < len(text) and text[i].isdigit():
                    i += 1
                text = text[i:].lstrip()
            values = np.array([float(x) for x in text.split(",") if x.strip()], dtype=np.float64)
            volts = self._scaled_volts(values, preamble)
            times = self._scaled_times_for_chunk(preamble, 1, volts.size)
            return times, volts, raw, preamble, transfer_pts_max

        if transfer_pts_max <= 0:
            transfer_pts_max = self.config.chunk_points

        chunk_pts = min(int(self.config.chunk_points), int(transfer_pts_max))
        if chunk_pts <= 0:
            chunk_pts = 16_000

        raw_parts: List[bytes] = []
        volts_parts: List[np.ndarray] = []
        times_parts: List[np.ndarray] = []

        start = 1
        while start <= acq_pts:
            stop = min(acq_pts, start + chunk_pts - 1)
            self.write(f":WAVeform:STARt {start}")
            self.write(f":WAVeform:STOP {stop}")

            raw = self._query_waveform_block()
            raw_parts.append(raw)

            values = self._decode_binary_values(raw, preamble)
            volts = self._scaled_volts(values, preamble)
            times = self._scaled_times_for_chunk(preamble, start, volts.size)

            volts_parts.append(volts)
            times_parts.append(times)

            start = stop + 1

        raw_all = b"".join(raw_parts)
        volts_all = np.concatenate(volts_parts) if volts_parts else np.array([], dtype=np.float64)
        times_all = np.concatenate(times_parts) if times_parts else np.array([], dtype=np.float64)

        return times_all, volts_all, raw_all, preamble, transfer_pts_max

    def save_classic_txt_and_log(self, ch: str, raw_data: bytes, preamble: Dict) -> None:
        if not self.config.filename:
            return

        base = f"{self.config.filename}_6000X_{ch.lower()}"
        txt_file = f"{base}.txt"
        log_file = f"{base}.log"

        if not self.config.force and (os.path.exists(txt_file) or os.path.exists(log_file)):
            raise FileExistsError(f"File exists: {txt_file} or {log_file} — use --force")

        with open(txt_file, "wb") as f:
            f.write(raw_data)

        with open(log_file, "w") as f:
            f.write(f"# Acquired: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Format:   {'ASCII' if self.config.ascii else 'BINARY'}\n")
            f.write(f"# Bytes:    {len(raw_data):,}\n")
            f.write(f"# Points:   {preamble['points']:,}\n")
            f.write(f"# Resource: {self.config.resource}\n")
            f.write(f"# Channels: {', '.join(self.config.channels)}\n\n")
            f.write(preamble["raw"] + "\n")

        logger.info(
            f"Saved classic files: {txt_file} + {log_file} ({preamble['points']:,} pts, {len(raw_data):,} bytes)"
        )

    def save_scaled_csv(self, ch: str, times: np.ndarray, voltages: np.ndarray) -> Optional[str]:
        if not self.config.filename or not self.config.csv:
            return None
        base = f"{self.config.filename}_6000X_{ch.lower()}"
        csv_file = f"{base}_scaled.csv"

        if not self.config.force and os.path.exists(csv_file):
            raise FileExistsError(f"CSV exists: {csv_file} — use --force")

        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time_s", "voltage_V"])
            for t, v in zip(times, voltages):
                writer.writerow([f"{t:.9e}", f"{v:.6e}"])

        if voltages.size:
            vmin = float(np.min(voltages))
            vmax = float(np.max(voltages))
            logger.info(f"Saved scaled CSV: {csv_file} ({len(times):,} pts, Vmin={vmin:.6g}, Vmax={vmax:.6g})")
        else:
            logger.info(f"Saved scaled CSV: {csv_file} ({len(times):,} pts)")
        return csv_file

    def _maybe_plot(self, channel_series: List[Tuple[str, np.ndarray, np.ndarray]]) -> None:
        if not self.config.plot:
            return

        try:
            import matplotlib.pyplot as plt
        except Exception as e:
            logger.error(f"--plot requested but matplotlib is not available: {e}")
            return

        plt.figure()
        for ch, t, v in channel_series:
            if t.size == 0 or v.size == 0:
                continue

            if t.size > self.config.plot_max_points:
                step = max(1, int(np.ceil(t.size / self.config.plot_max_points)))
                t_plot = t[::step]
                v_plot = v[::step]
                logger.info(f"{ch} plot decimated: {t.size:,} → {t_plot.size:,} (step={step})")
            else:
                t_plot, v_plot = t, v

            plt.plot(t_plot, v_plot, label=ch)

        plt.xlabel("time (s)")
        plt.ylabel("voltage (V)")
        plt.title("Captured Waveform (scaled)")
        if len(channel_series) > 1:
            plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    def acquire_and_save(self) -> None:
        self.configure_waveform_format()
        self.set_max_record_length()

        logger.info("Trigger → AUTO + Force")
        self.write(":TRIGger:SWEep AUTO")
        self.write(":TRIGger:FORCe")
        time.sleep(0.8)

        ch_list = ",".join(self.config.channels)
        logger.info(f"Starting acquisition: :DIGitize {ch_list}")
        self.write(f":DIGitize {ch_list}")
        self._wait_opc(timeout_sec=300.0)

        try:
            acq_pts = int(float(self.query(":ACQuire:POINts?")))
            logger.info(f"Instrument :ACQ:POINts? = {acq_pts:,}")
        except Exception:
            pass

        for ch in self.config.channels:
            try:
                wav_pts_report = self.query(":WAVeform:POINts?")
                logger.info(f"{ch} :WAV:POINts? (instrument reports) = {wav_pts_report}")
            except Exception:
                pass

        plotted: List[Tuple[str, np.ndarray, np.ndarray]] = []

        for ch in self.config.channels:
            logger.info(f"Downloading waveform {ch} ...")

            times, volts, raw_all, preamble, transfer_pts_max = self.download_waveform_scaled(ch)
            self._log_waveform_summary(ch, preamble, len(raw_all), transfer_pts_max)

            self.save_classic_txt_and_log(ch, raw_all, preamble)
            self.save_scaled_csv(ch, times, volts)

            plotted.append((ch, times, volts))

        self.write(":RUN")
        logger.info("Acquisition complete – back to RUN mode")

        self._maybe_plot(plotted)

    def setup_and_acquire(self) -> None:
        if self.config.autoset:
            self.autoset()
        self.acquire_and_save()

    def close(self) -> None:
        try:
            if self.scope:
                self.scope.close()
        finally:
            self.rm.close()
        logger.info("LAN connection closed.")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Acquire waveforms from Keysight DSO-X 6000 series over LAN (correct scaling + chunked download).",
    )
    parser.add_argument("-c", "--channels", type=str, default="CHAN1")
    parser.add_argument("-r", "--resource", type=str, default=DEFAULT_RESOURCE)
    parser.add_argument("-f", "--filename", type=str, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout", type=float, default=40.0)
    parser.add_argument("--autoset", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--ascii", action="store_true", help="Use ASCII format (slower/limited)")
    parser.add_argument("--csv", action="store_true", help="Save scaled time,voltage CSV")
    parser.add_argument("--no-max-points", action="store_false", dest="max_points")
    parser.add_argument("--chunk-points", type=int, default=250_000, help="Chunk size for binary transfer")
    parser.add_argument("--plot", action="store_true", help="Plot scaled waveform(s) after acquisition")
    parser.add_argument(
        "--plot-max-points",
        type=int,
        default=300_000,
        help="Max points to draw per channel (auto-decimates if larger)",
    )
    parser.add_argument("--config-save", type=str, default=None)
    parser.add_argument("--config-load", type=str, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.config_load:
        try:
            config = OscilloscopeConfig.load_from_file(args.config_load)
        except Exception as e:
            logger.error(f"Config load failed: {e}")
            sys.exit(1)
    else:
        channels = [ch.strip() for ch in args.channels.split(",") if ch.strip()]
        try:
            config = OscilloscopeConfig(
                channels=channels,
                resource=args.resource,
                filename=args.filename,
                force=args.force,
                timeout=args.timeout,
                autoset=args.autoset,
                ascii=args.ascii,
                max_points=args.max_points,
                csv=args.csv,
                chunk_points=args.chunk_points,
                plot=args.plot,
                plot_max_points=args.plot_max_points,
            )
        except ValidationError as e:
            logger.error(f"Invalid config: {e}")
            sys.exit(1)

    if args.config_save:
        try:
            config.save_to_file(args.config_save)
        except Exception as e:
            logger.error(f"Config save failed: {e}")
            sys.exit(1)

    scope = None
    try:
        scope = KeysightInfiniiVision6000X(config)
        if args.reset:
            scope.reset()
        scope.setup_and_acquire()
    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if scope:
            scope.close()


if __name__ == "__main__":
    main()
"""EPILOG = \
Examples
--------
# USB (recommended): capture CH1, save CSV, and plot
  %(prog)s -r "USB0::2391::6017::MY61500116::INSTR" -c CHAN1 -f cap --force --csv --plot

# LAN:
  %(prog)s -r "TCPIP0::192.168.1.14::INSTR" -c CHAN1 -f cap --force --csv --plot

# Dual-channel capture (binary), chunked download will fetch full record:
  %(prog)s -c CHAN1,CHAN2 -f dual --force --csv --plot

# Change chunk size (use smaller chunks if your USB/VISA stack is finicky):
  %(prog)s -c CHAN1 -f cap --force --csv --chunk-points 50000

# Keep the scope's current record length (do not attempt :ACQ:POIN):
  %(prog)s -c CHAN1 -f cap --force --csv --no-max-points

# ASCII mode (slow/limited; only use if you must):
  %(prog)s -c CHAN1 -f cap --force --csv --ascii

Notes
-----
- The script always uses :WAV:POIN:MODE RAW and requests :WAV:POIN MAX, but some firmware limits
  single transfers (often 16k points). In that case the script automatically downloads the full
  acquisition using :WAV:STAR/:WAV:STOP chunking.
- --plot displays the scaled waveform after acquisition; large captures are auto-decimated for speed.
- If using USB and you get VISA errors with pyvisa-py, install NI-VISA (system VISA) and the script
  will auto-fallback to it.
"""
