#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

"""
Minimal USB waveform capture for Keysight DSO-X 6002A (and similar InfiniiVision 6000 X-Series)
- Uses binary BYTE format + chunked download (:WAV:STARt / :WAV:STOP)
- Saves scaled CSV: time_s, voltage_V
- Tested workarounds: longer timeout + small chunks + Compatibility Mode recommended
"""

import sys
import time
import csv
import argparse
import numpy as np
import pyvisa

# ────────────────────────────────────────────────
DEFAULT_RESOURCE = "USB0::2391::6017::MY61500116::INSTR"
DEFAULT_CHUNK    = 8000          # small → helps avoid USB stalls
DEFAULT_TIMEOUT  = 120.0         # seconds – generous for USB
# ────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Simple USB waveform capture → scaled CSV")
    parser.add_argument("-c", "--channel",   default="CHAN1",    help="Channel: CHAN1, CHAN2, ... (default: CHAN1)")
    parser.add_argument("-f", "--filename",  required=True,      help="Output base name (e.g. 'capture' → capture_CHAN1_scaled.csv)")
    parser.add_argument("--force",           action="store_true", help="Overwrite existing files")
    parser.add_argument("--chunk",           type=int, default=DEFAULT_CHUNK, help=f"Points per chunk (default: {DEFAULT_CHUNK})")
    parser.add_argument("--timeout",         type=float, default=DEFAULT_TIMEOUT, help=f"Visa timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--no-autoscale",    action="store_false", dest="autoscale", help="Skip :AUToscale")
    return parser.parse_args()


def main():
    args = parse_args()

    csv_path = f"{args.filename}_{args.channel}_scaled.csv"
    if not args.force:
        try:
            with open(csv_path): pass
            print(f"Error: {csv_path} already exists → use --force to overwrite")
            sys.exit(1)
        except FileNotFoundError:
            pass

    rm = pyvisa.ResourceManager("@py")          # try "@ni" if you install NI/Keysight VISA
    try:
        scope = rm.open_resource(DEFAULT_RESOURCE)
        scope.timeout = int(args.timeout * 1000)    # ms
        scope.read_termination  = "\n"
        scope.write_termination = "\n"
        scope.chunk_size = 32768

        print(f"Connected: {scope.query('*IDN?').strip()}")
    except Exception as e:
        print(f"Cannot open resource: {e}")
        sys.exit(1)

    def w(cmd):    scope.write(cmd)
    def q(cmd):    return scope.query(cmd).strip()
    def wait_opc(timeout=180):
        start = time.time()
        while time.time() - start < timeout:
            if q("*OPC?") == "1": return
            time.sleep(0.3)
        print("Warning: OPC timeout — continuing")

    try:
        # ─── Preparation ───────────────────────────────────────
        w("*CLS")                           # clear status
        if args.autoscale:
            print("Running :AUToscale ...")
            w(":AUToscale")
            wait_opc(60)

        w(f":WAVeform:SOURce {args.channel}")
        w(":WAVeform:FORMat BYTE")          # 8-bit → fast & compact
        w(":WAVeform:BYTorder LSBFirst")
        w(":WAVeform:POINts:MODE RAW")

        # Get scaling factors (preamble)
        preamble_str = q(":WAVeform:PREamble?")
        vals = [float(x) for x in preamble_str.split(",")]
        if len(vals) < 10:
            raise RuntimeError(f"Bad preamble: {preamble_str}")

        format_, typ, points, count, xinc, xorg, xref, yinc, yorg, yref = vals
        points = int(points)
        print(f"Acquisition points: {points:,}")
        print(f"Scaling: yinc={yinc:.3e}  yorg={yorg:.6g}  yref={yref:.0f}")

        # ─── Force trigger & digitize ──────────────────────────
        print("Triggering ...")
        w(":TRIGger:SWEep AUTO")
        w(":TRIGger:FORCe")
        time.sleep(0.5)
        w(f":DIGitize {args.channel}")
        wait_opc(300)

        # ─── Chunked binary download ───────────────────────────
        all_times = []
        all_volts = []
        start_idx = 1

        while start_idx <= points:
            stop_idx = min(points, start_idx + args.chunk - 1)
            print(f"  Fetching {start_idx:8d} → {stop_idx:8d}  ({stop_idx - start_idx + 1:,} pts)")

            w(f":WAVeform:STARt {start_idx}")
            w(f":WAVeform:STOP  {stop_idx}")
            w(":WAVeform:DATA?")

            # Read IEEE block
            header = scope.read_bytes(2)
            if header[0:1] != b"#":
                raise RuntimeError(f"Bad block header: {header!r}")

            n_digits = int(header[1:2])
            len_bytes = int(scope.read_bytes(n_digits))
            raw = scope.read_bytes(len_bytes)
            scope.read_bytes(1)  # NL

            values = np.frombuffer(raw, dtype=np.uint8)
            volts = (values.astype(float) - yref) * yinc + yorg

            # Time axis
            idx0 = start_idx - 1
            times = (np.arange(len(volts), dtype=float) + idx0 - xref) * xinc + xorg

            all_volts.append(volts)
            all_times.append(times)

            start_idx = stop_idx + 1

        all_times = np.concatenate(all_times)
        all_volts = np.concatenate(all_volts)

        # ─── Save scaled CSV ───────────────────────────────────
        print(f"Saving {len(all_times):,} points → {csv_path}")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time_s", "voltage_V"])
            for t, v in zip(all_times, all_volts):
                writer.writerow([f"{t:.9e}", f"{v:.6e}"])

        vmin, vmax = float(all_volts.min()), float(all_volts.max())
        print(f"Done. V range: {vmin:.6g} V → {vmax:.6g} V")

        w(":RUN")   # back to live mode

    except pyvisa.errors.VisaIOError as e:
        print(f"VISA error: {e}")
        if e.error_code == -1073807339:   # VI_ERROR_TMO
            print("\nTimeout → try these:")
            print("  1. Enable USB Compatibility Mode on scope (Utility → I/O → Configure USB)")
            print("  2. Use smaller --chunk (e.g. 4000)")
            print("  3. Increase --timeout (e.g. 300)")
            print("  4. Install Keysight IO Libraries → change ResourceManager() to default")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        scope.close()
        rm.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()
