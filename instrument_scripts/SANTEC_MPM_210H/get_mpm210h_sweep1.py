#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
"""
MPM-210H Sweep Measurement Script via GPIB Connection

This script performs an optical power measurement over a specified wavelength range
using the SWEEP measurement mode (SWEEP1). It configures the instrument with the provided 
sweep parameters—start wavelength, stop wavelength, wavelength step, sweep speed, TIA gain,
and trigger mode—and starts the measurement. Measurement data is saved to a specified file, 
meta-information can optionally be saved, system state and settings are logged, and you can 
also plot the sweep.

Usage Examples:
--------------
1. Perform sweep and plot:
   $ ./get_mpm210h_sweep1.py sweep \
       --start 1260 --stop 1290 --step 0.01 --speed 10 --gain 1 \
       --data-file sweep_data.csv --log-file system_log.txt \
       --plot

2. Perform sweep, save data, and plot:
   $ ./get_mpm210h_sweep1.py sweep \
       --data-file sweep_data.csv --log-file system_log.txt \
       --start 1260 --stop 1290 --step 0.01 --speed 10 --gain 1 \
       --plot

3. Perform sweep, save data, meta, log, and plot:
   $ ./get_mpm210h_sweep1.py sweep \
       --data-file sweep_data.csv --meta-file sweep_meta.txt \
       --log-file system_log.txt \
       --start 1260 --stop 1290 --step 0.01 --speed 10 --gain 1 \
       --trigger internal --plot
"""

import sys
import logging
import argparse
import pyvisa as visa
import time
import struct
import numpy as np
import matplotlib.pyplot as plt

# Configure logging for detailed output.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class MPM210H:
    """
    Handles communication with the MPM-210H instrument.
    Implements a context manager for proper resource handling.
    """
    def __init__(self, resource):
        self.resource = resource

    def __enter__(self):
        try:
            rm = visa.ResourceManager('@py')
            self.device = rm.open_resource(self.resource)
            self.device.timeout = 15000  # 15 seconds timeout
            self.device.read_termination = "\n"
            self.device.write_termination = "\n"
            logging.info(f"Connected to resource: {self.resource}")
        except Exception as e:
            logging.error(f"Could not open resource {self.resource}: {e}")
            sys.exit(1)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.device.close()
            logging.info("Device connection closed.")
        except Exception as e:
            logging.error(f"Error closing connection: {e}")

    def send_command(self, cmd: str):
        logging.info(f"Sending command: {cmd}")
        try:
            self.device.write(cmd)
        except Exception as e:
            logging.error(f"Error sending command: {e}")
            sys.exit(1)

    def query(self, cmd: str) -> str:
        logging.info(f"Querying with command: {cmd}")
        try:
            self.device.write(cmd)
            return self.device.read().strip()
        except Exception as e:
            logging.error(f"Error during query '{cmd}': {e}")
            sys.exit(1)

    def query_binary_block(self, cmd: str) -> bytes:
        """
        Query a binary block (e.g. LOGG?) and return the full raw bytes.
        """
        logging.info(f"Querying binary block with command: {cmd}")
        try:
            self.device.write(cmd)
            # read_raw returns the full IEEE block including header
            raw = self.device.read_raw()
            return raw
        except Exception as e:
            logging.error(f"Error reading binary block '{cmd}': {e}")
            sys.exit(1)

def parse_ieee_block(raw: bytes) -> np.ndarray:
    """
    Parse an IEEE 488.2 definite-length binary block:
      #<digit><len><data>
    where <len> is ASCII digits of length <digit>, and <data> is <len> bytes
    of big-endian IEEE754 floats.
    """
    if not raw.startswith(b"#"):
        raise ValueError("Invalid block header")
    ndigits = int(raw[1:2])
    length = int(raw[2:2+ndigits])
    data = raw[2+ndigits : 2+ndigits+length]
    # Each float32 is 4 bytes, big-endian
    count = length // 4
    return np.array(struct.unpack(f">{count}f", data))

def perform_sweep_measurement(mpm, start, stop, step, speed, gain, trigger):
    """
    Configure and run sweep1. Returns wavelengths array and power array.
    """
    mpm.send_command("WMOD SWEEP1")
    mpm.send_command(f"WSET {start},{stop},{step}")
    mpm.send_command(f"SPE {speed}")
    mpm.send_command(f"LEV {gain}")
    trig_val = 0 if trigger.lower()=="internal" else 1
    mpm.send_command(f"TRIG {trig_val}")
    time.sleep(0.5)

    mpm.send_command("MEAS")
    # Poll status
    while True:
        stat = mpm.query("STAT?")
        if stat.split(",")[0] == "1":
            logging.info("Measurement complete.")
            break
        logging.info("Waiting for measurement to finish...")
        time.sleep(0.5)
    mpm.send_command("STOP")

    # Fetch binary data
    raw = mpm.query_binary_block("LOGG? 0,1")
    powers = parse_ieee_block(raw)

    # Build wavelength axis
    npts = powers.size
    wavelengths = np.linspace(start, stop, npts)
    return wavelengths, powers

def query_sweep_meta_info(mpm):
    meta = {}
    meta["WMOD?"]   = mpm.query("WMOD?")
    meta["WSET?"]   = mpm.query("WSET?")
    meta["SPE?"]    = mpm.query("SPE?")
    meta["LEV?"]    = mpm.query("LEV?")
    meta["TRIG?"]   = mpm.query("TRIG?")
    return meta

def log_system_state(mpm, fn):
    """
    Log system state and settings to a file.
    """
    system_info = {}
    try:
        system_info["Instrument ID"] = mpm.query("*IDN?")  # Standard SCPI identification query
        system_info["System Status"] = mpm.query("STAT?")  # Current system status
        system_info["Error Status"] = mpm.query("ERR?")    # Error status
        system_info["Timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        system_info["Resource"] = mpm.resource
    except Exception as e:
        logging.error(f"Error querying system state: {e}")
        system_info["Error"] = str(e)

    with open(fn, 'w') as f:
        for k, v in system_info.items():
            f.write(f"{k}: {v}\n")
    logging.info(f"Saved system state to {fn}")

def save_data(fn, wavelengths, powers):
    """Save CSV with two columns: wavelength, power."""
    import csv
    with open(fn, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Wavelength(nm)","Power"])
        writer.writerows(zip(wavelengths, powers))
    logging.info(f"Saved sweep data to {fn}")

def save_meta(fn, meta):
    with open(fn, 'w') as f:
        for k, v in meta.items():
            f.write(f"{k}: {v}\n")
    logging.info(f"Saved meta-info to {fn}")

def plot_sweep(wavelengths, powers, title="Sweep Measurement"):
    plt.figure()
    plt.plot(wavelengths, powers)
    plt.xlabel("Wavelength (nm)")
    plt.ylabel("Optical Power")
    plt.title(title)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.savefig('sweep_plot.png')  # Save plot as file
    logging.info("Saved sweep plot to sweep_plot.png")

def main():
    p = argparse.ArgumentParser()
    subs = p.add_subparsers(dest="cmd", required=True)

    sw = subs.add_parser("sweep", help="Perform sweep1 measurement")
    sw.add_argument("--data-file", required=True, help="CSV file to save data")
    sw.add_argument("--meta-file", help="File to save meta-information")
    sw.add_argument("--log-file", required=True, help="File to save system state and settings")
    sw.add_argument("--start", type=float, default=1260)
    sw.add_argument("--stop",  type=float, default=1290)
    sw.add_argument("--step",  type=float, default=0.01)
    sw.add_argument("--speed", type=float, default=10)
    sw.add_argument("--gain",  type=int,   default=1)
    sw.add_argument("--trigger", choices=["internal","external"], default="internal")
    sw.add_argument("--plot", action="store_true", help="Plot the sweep data")

    args = p.parse_args()
    resource = "GPIB0::16::INSTR"

    with MPM210H(resource) as mpm:
        if args.cmd=="sweep":
            # Log system state and settings
            log_system_state(mpm, args.log_file)
            wl, pw = perform_sweep_measurement(mpm,
                                               args.start, args.stop,
                                               args.step, args.speed,
                                               args.gain, args.trigger)
            save_data(args.data_file, wl, pw)
            if args.meta_file:
                meta = query_sweep_meta_info(mpm)
                save_meta(args.meta_file, meta)
            if args.plot:
                plot_sweep(wl, pw)

if __name__=="__main__":
    main()