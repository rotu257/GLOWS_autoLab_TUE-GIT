#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
"""
PM400 power readout helper.

Adds:
  - --stable: only accept/safe-save once readings are stable
  - --show: print current reading and exit (no file)
Default unit: W (watts)

SCPI notes:
  - Power unit: SENS:POW:UNIT {W|DBM}
  - Autorange:  SENS:POW:RANG:AUTO {ON|OFF}
  - Range set:  SENS:POW:RANG:UPP <value>W
From PM400 SCPI reference. :contentReference[oaicite:0]{index=0}
"""

from __future__ import annotations

import math
import os
import statistics
import sys
import time
from dataclasses import dataclass
from optparse import OptionParser
from typing import Iterable, List, Optional, Tuple

import pyvisa as visa


@dataclass(frozen=True)
class StabilityConfig:
    enabled: bool
    samples: int
    interval_s: float
    window: int
    rel_tol: float
    abs_tol_w: float
    max_wait_s: float
    autorange: bool
    set_manual_range: bool
    range_headroom: float
    min_sig_figs: int
    max_sig_figs: int


class PM400:
    def __init__(
        self,
        query: Optional[str] = None,
        command: Optional[str] = None,
        wavelength: Optional[float] = None,
        force: bool = False,
        filename: Optional[str] = None,
        save: bool = True,
        resource_str: Optional[str] = None,
        retries: int = 3,
        unit: str = "W",
        show: bool = False,
        stability: Optional[StabilityConfig] = None,
    ) -> None:
        rm = visa.ResourceManager()
        if resource_str is None:
            resource_str = "USB0::4883::32885::P5002928::0::INSTR"

        try:
            self.instrument = rm.open_resource(resource_str)
        except Exception as e:
            print(f"Error opening resource {resource_str}: {e}")
            sys.exit(1)

        self.instrument.write("*RST")
        self.instrument.write("CONFigure:SCALar:POWer")  # measurement mode
        self._set_unit(unit)

        if wavelength is not None:
            self.set_wavelength(wavelength)

        if query:
            print("\nAnswer to query:", query)
            self.instrument.write(query)
            rep = self.instrument.read()
            print(rep, "\n")
            sys.exit(0)

        if command:
            print("\nExecuting command:", command)
            self.instrument.write(command)
            sys.exit(0)

        if show:
            reading = self._read_one_value_w(retries=retries)
            if stability and stability.enabled:
                stable_val, meta = self.get_stable_power_w(stability, retries=retries)
                print(self._format_value_with_unit(stable_val, unit), f"  {meta}")
            else:
                print(self._format_value_with_unit(reading, unit))
            sys.exit(0)

        if filename:
            if stability and stability.enabled:
                val_w, meta = self.get_stable_power_w(stability, retries=retries)
                data_str = self._format_value_with_unit(val_w, unit)
                print(meta)
            else:
                val_w = self._read_one_value_w(retries=retries)
                data_str = self._format_value_with_unit(val_w, unit)

            if save:
                out_name = f"{filename}_PM400"
                if os.path.exists(out_name) and not force:
                    print(f"\nFile {out_name} already exists. Use -F option to force overwriting.\n")
                    sys.exit(1)
                with open(out_name, "w", encoding="utf-8") as f:
                    f.write(data_str + "\n")
                print(f"Data saved to {out_name}")

    # -------------------- Instrument config --------------------

    def _write_try(self, cmd: str) -> bool:
        try:
            self.instrument.write(cmd)
            return True
        except Exception:
            return False

    def _set_unit(self, unit: str) -> None:
        unit = unit.strip().upper()
        if unit not in {"W", "DBM"}:
            print("Error: unit must be W or DBM.")
            sys.exit(1)

        # Prefer the documented short form; fall back to common DC variants.
        if self._write_try(f"SENS:POW:UNIT {unit}"):
            return
        if self._write_try(f"SENS:POW:DC:UNIT {unit}"):
            return
        # Last resort: some firmwares accept "SENS:POW:UNIT" only after config;
        # if we still fail, warn but continue.
        print(f"Warning: could not set unit via SCPI (requested {unit}).")

    def set_wavelength(self, wavelength: float) -> None:
        """
        Set the wavelength for the power meter in nanometers.
        """
        try:
            wl = float(wavelength)
        except ValueError:
            print("Error: Wavelength must be a number (in nanometers).")
            sys.exit(1)

        if wl < 200 or wl > 2500:
            print(f"Error: Wavelength {wl} nm is out of valid range (200-2500 nm).")
            sys.exit(1)

        print(f"Setting wavelength to {wl} nm")
        self.instrument.write(f"SENS:CORR:WAV {wl}")

    def _set_autorange(self, enabled: bool) -> None:
        state = "ON" if enabled else "OFF"
        # From PM400 SCPI table: POWer[:DC] RANGe AUTO {OFF|ON}. :contentReference[oaicite:1]{index=1}
        if self._write_try(f"SENS:POW:RANG:AUTO {state}"):
            return
        self._write_try(f"SENS:POW:DC:RANG:AUTO {state}")

    def _set_manual_range_upper_w(self, upper_w: float) -> None:
        if upper_w <= 0:
            return
        # From PM400 SCPI table: POWer[:DC] RANGe [:UPPer] <numeric>[W]. :contentReference[oaicite:2]{index=2}
        if self._write_try(f"SENS:POW:RANG:UPP {upper_w}W"):
            return
        self._write_try(f"SENS:POW:DC:RANG:UPP {upper_w}W")

    # -------------------- Reading + validation --------------------

    def _read_raw(self) -> str:
        self.instrument.write("READ?")  # start new measurement and read data :contentReference[oaicite:3]{index=3}
        return str(self.instrument.read()).strip()

    @staticmethod
    def _parse_float(s: str) -> Optional[float]:
        try:
            v = float(s)
        except ValueError:
            return None
        if math.isnan(v) or math.isinf(v):
            return None
        return v

    def _read_one_value_w(self, retries: int = 3) -> float:
        attempt = 0
        while attempt <= retries:
            try:
                raw = self._read_raw()
                v = self._parse_float(raw)
                if v is None:
                    raise ValueError(f"invalid numeric: {raw}")
                return v
            except Exception as e:
                if attempt < retries:
                    time.sleep(0.25)
                    attempt += 1
                    continue
                self._log_invalid_measurement(f"Error: {e}")
                raise RuntimeError(f"Unable to acquire valid measurement after {retries} retries") from e
        raise RuntimeError("unreachable")

    def _log_invalid_measurement(self, data: str) -> None:
        with open("invalid_measurements.log", "a", encoding="utf-8") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] Invalid measurement: {data}\n")

    # -------------------- Stability + formatting --------------------

    @staticmethod
    def _stable_stats(values: List[float]) -> Tuple[float, float, float]:
        mean = statistics.fmean(values)
        if len(values) < 2:
            return mean, 0.0, 0.0
        stdev = statistics.pstdev(values)
        if mean == 0.0:
            rel = float("inf") if stdev != 0.0 else 0.0
        else:
            rel = stdev / abs(mean)
        return mean, stdev, rel

    @staticmethod
    def _sig_figs_from_noise(
        mean: float,
        stdev: float,
        min_sig: int,
        max_sig: int,
    ) -> int:
        """
        Choose sig-figs so the last digit is not dominated by noise.
        """
        if mean == 0.0:
            # If we're near zero, use a conservative fixed sig-fig count.
            return min(max_sig, max(min_sig, 3))

        if stdev <= 0.0:
            return min(max_sig, max(min_sig, 6))

        ratio = stdev / abs(mean)
        # If ratio=1e-3 (~0.1%), we can show ~3 meaningful digits beyond first digit.
        est = int(max(0, math.floor(-math.log10(ratio))) + 1)
        return max(min_sig, min(max_sig, est))

    @staticmethod
    def _format_sig_figs(x: float, sig_figs: int) -> str:
        if x == 0.0:
            return "0"
        return f"{x:.{sig_figs}g}"

    def _format_value_with_unit(self, value_w: float, unit: str) -> str:
        unit = unit.upper()
        if unit == "W":
            # keep in watts, just format nicely
            return f"{value_w:.12g} W"
        if unit == "DBM":
            # convert W -> dBm for display if needed
            if value_w <= 0:
                return "-inf dBm"
            dbm = 10.0 * math.log10(value_w / 1e-3)
            return f"{dbm:.6g} dBm"
        return f"{value_w:.12g} {unit}"

    def get_stable_power_w(self, cfg: StabilityConfig, retries: int = 3) -> Tuple[float, str]:
        """
        Acquire values until stable, then return mean of last window.
        Stability condition (last window):
          - stdev <= abs_tol_w  OR  (stdev/|mean|) <= rel_tol
        Also optionally autoranges + sets a manual upper range based on observed max.
        """
        if cfg.autorange:
            self._set_autorange(True)

        start = time.time()
        values: List[float] = []
        last_range_set = False

        while True:
            if (time.time() - start) > cfg.max_wait_s:
                # Best-effort: return mean of what we have.
                tail = values[-cfg.window :] if len(values) >= cfg.window else values
                mean, stdev, rel = self._stable_stats(tail) if tail else (float("nan"), float("nan"), float("nan"))
                meta = f"[stable-timeout] n={len(values)} mean={mean:.6g}W stdev={stdev:.3g}W rel={rel:.3g}"
                return mean, meta

            v = self._read_one_value_w(retries=retries)
            values.append(v)

            # After a few samples, optionally lock a manual range (keeps display/ADC from hopping).
            if cfg.set_manual_range and not last_range_set and len(values) >= max(5, cfg.window):
                vmax = max(values)
                upper = max(vmax * cfg.range_headroom, 1e-12)
                self._set_manual_range_upper_w(upper)
                if cfg.autorange:
                    self._set_autorange(False)
                last_range_set = True

            if len(values) < max(cfg.window, 2):
                time.sleep(cfg.interval_s)
                continue

            tail = values[-cfg.window :]
            mean, stdev, rel = self._stable_stats(tail)

            stable = (stdev <= cfg.abs_tol_w) or (rel <= cfg.rel_tol)
            if stable:
                sig = self._sig_figs_from_noise(mean, stdev, cfg.min_sig_figs, cfg.max_sig_figs)
                formatted = self._format_sig_figs(mean, sig)
                meta = (
                    f"[stable] n={len(values)} window={cfg.window} "
                    f"mean={formatted}W stdev={stdev:.3g}W rel={rel:.3g} sigfigs={sig}"
                )
                return mean, meta

            time.sleep(cfg.interval_s)


def build_parser() -> OptionParser:
    usage = """usage: %prog [options]

Examples:
  Save a measurement:
      get_pm400 -o measurement_file

  Show current reading (no save):
      get_pm400 --show

  Wait for stable value before saving:
      get_pm400 --stable -o measurement_file

  Stable + tighter threshold (0.2% relative) and longer averaging window:
      get_pm400 --stable --stable-rel 0.002 --stable-window 10 -o measurement_file

  Set wavelength then stable-save:
      get_pm400 -w 532 --stable -o measurement_file
"""
    parser = OptionParser(usage=usage)

    parser.add_option("-q", "--query", type="str", dest="query", default=None,
                      help="SCPI query string to send (e.g. '*IDN?').")
    parser.add_option("-c", "--command", type="str", dest="command", default=None,
                      help="SCPI command string to send.")
    parser.add_option("-r", "--resource", type="str", dest="resource", default=None,
                      help="VISA resource string (default: PM400 USB resource).")
    parser.add_option("-o", "--filename", type="string", dest="filename", default=None,
                      help="Base name of output file (writes <name>_PM400).")
    parser.add_option("-F", "--force", action="store_true", dest="force", default=False,
                      help="Allow overwriting output file if it exists.")
    parser.add_option("-w", "--wavelength", type="float", dest="wavelength", default=None,
                      help="Set wavelength in nm (e.g. 532).")
    parser.add_option("--retries", type="int", dest="retries", default=3,
                      help="Retries for invalid reads (default: 3).")

    # Display/unit options
    parser.add_option("--show", action="store_true", dest="show", default=False,
                      help="Print current reading and exit (no file write).")
    parser.add_option("--unit", type="str", dest="unit", default="W",
                      help="Measurement unit: W or DBM (default: W).")

    # Stability options
    parser.add_option("--stable", action="store_true", dest="stable", default=False,
                      help="Wait for a stable reading before printing/saving.")
    parser.add_option("--stable-samples", type="int", dest="stable_samples", default=40,
                      help="Max samples to take while trying to stabilize (soft limit; default: 30).")
    parser.add_option("--stable-interval", type="float", dest="stable_interval", default=0.10,
                      help="Seconds between samples (default: 0.10).")
    parser.add_option("--stable-window", type="int", dest="stable_window", default=7,
                      help="Window size (last N samples) used for stability test (default: 7).")
    parser.add_option("--stable-rel", type="float", dest="stable_rel", default=0.005,
                      help="Relative stability threshold (stdev/|mean|) (default: 0.005 = 0.5%%).")
    parser.add_option("--stable-abs", type="float", dest="stable_abs", default=0.0,
                      help="Absolute stability threshold in W (default: 0 disables absolute check).")
    parser.add_option("--stable-max-wait", type="float", dest="stable_max_wait", default=10.0,
                      help="Max seconds to wait for stability before returning best-effort (default: 10).")
    parser.add_option("--stable-autorange", action="store_true", dest="stable_autorange", default=True,
                      help="Enable autoranging during stabilization (default: ON).")
    parser.add_option("--stable-no-autorange", action="store_false", dest="stable_autorange",
                      help="Disable autoranging during stabilization.")
    parser.add_option("--stable-set-range", action="store_true", dest="stable_set_range", default=True,
                      help="After a few samples, lock a manual range based on observed max (default: ON).")
    parser.add_option("--stable-no-set-range", action="store_false", dest="stable_set_range",
                      help="Do not lock a manual range (leave autorange/manual as configured).")
    parser.add_option("--stable-range-headroom", type="float", dest="stable_range_headroom", default=1.5,
                      help="Manual range upper = headroom * observed max (default: 1.5).")
    parser.add_option("--stable-min-sigfigs", type="int", dest="stable_min_sigfigs", default=3,
                      help="Minimum sig-figs for stable print/save formatting (default: 3).")
    parser.add_option("--stable-max-sigfigs", type="int", dest="stable_max_sigfigs", default=8,
                      help="Maximum sig-figs for stable print/save formatting (default: 8).")

    return parser


def main() -> None:
    parser = build_parser()
    (options, _args) = parser.parse_args()

    unit = (options.unit or "W").strip().upper()
    if unit not in {"W", "DBM"}:
        print("Error: --unit must be W or DBM.")
        sys.exit(1)

    stability = StabilityConfig(
        enabled=bool(options.stable),
        samples=int(options.stable_samples),
        interval_s=float(options.stable_interval),
        window=int(options.stable_window),
        rel_tol=float(options.stable_rel),
        abs_tol_w=float(options.stable_abs),
        max_wait_s=float(options.stable_max_wait),
        autorange=bool(options.stable_autorange),
        set_manual_range=bool(options.stable_set_range),
        range_headroom=float(options.stable_range_headroom),
        min_sig_figs=int(options.stable_min_sigfigs),
        max_sig_figs=int(options.stable_max_sigfigs),
    )

    # If user didn't pass -o, we still allow --show or queries/commands.
    PM400(
        query=options.query,
        command=options.command,
        wavelength=options.wavelength,
        force=options.force,
        filename=options.filename,
        save=True,
        resource_str=options.resource,
        retries=options.retries,
        unit=unit,
        show=options.show,
        stability=stability,
    )


if __name__ == "__main__":
    main()
