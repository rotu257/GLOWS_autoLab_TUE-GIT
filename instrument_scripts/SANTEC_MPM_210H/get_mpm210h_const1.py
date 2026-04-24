#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

"""
MPM-210H Measurement Script via GPIB Connection

This script performs optical power measurement at a fixed wavelength
(using the CONST1 measurement mode) and saves the measurement data to a file.
It also provides an option to save meta-information about the instrument's current
measurement settings (such as measurement mode, wavelength, unit, auto-range status, etc.)
to a separate file, and an option to plot the 4-channel data.
Additionally, you can now specify the measurement unit (DBM or W).
A log file is generated to capture system state and instrument settings.

Usage Examples:
--------------
1. Measure optical power in dBm and save data:
   $ ./get_mpm210h_const1.py measure --unit DBM --data-file measurement_data

2. Measure optical power in Watts and additionally save meta-information:
   $ ./get_mpm210h_const1.py measure --unit W --data-file measurement_data --meta-file measurement_meta.txt

3. Measure, save data, meta, and plot in Watts:
   $ ./get_mpm210h_const1.py measure --unit W --data-file measurement_data --meta-file measurement_meta.txt --plot
"""

import sys
import logging
import argparse
import pyvisa as visa
import time
import matplotlib.pyplot as plt
import numpy as np
import platform
from datetime import datetime

# Configure logging to write to both file and console
log_file = "mpm210h_log.txt"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),  # Log to file
        logging.StreamHandler(sys.stdout)  # Log to console
    ]
)

# Hard-coded setting for GPIB connection
GPIB_ADDRESS = "GPIB0::16::INSTR"

class MPM210H:
    def __init__(self, resource):
        self.resource = resource

    def __enter__(self):
        try:
            rm = visa.ResourceManager('@py')
            self.device = rm.open_resource(self.resource)
            self.device.timeout = 10000
            self.device.read_termination = "\n"
            self.device.write_termination = "\n"
            logging.info(f"Connected to {self.resource}")
        except Exception as e:
            logging.error(f"Could not open resource {self.resource}: {e}")
            sys.exit(1)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        try:
            self.device.close()
            logging.info("Connection closed")
        except:
            pass

    def send(self, cmd):
        logging.info(f"> {cmd}")
        self.device.write(cmd)

    def query(self, cmd):
        logging.info(f"? {cmd}")
        response = self.device.query(cmd).strip()
        logging.info(f"< {response}")
        return response

def perform_measurement(mpm):
    # Set to constant measurement mode
    mpm.send("WMOD CONST1")
    time.sleep(0.5)
    return mpm.query("READ? 0")

def query_meta(mpm):
    return {
        "WMOD?": mpm.query("WMOD?"),
        "WAV?":  mpm.query("WAV?"),
        "UNIT?": mpm.query("UNIT?"),
        "AUTO?": mpm.query("AUTO?"),
        "DAUTO? 0": mpm.query("DAUTO? 0")
    }

def save_data(fn, raw):
    with open(fn, 'w') as f:
        f.write(raw + "\n")
    logging.info(f"Data saved to {fn}")

def save_meta(fn, meta):
    with open(fn, 'w') as f:
        for k, v in meta.items():
            f.write(f"{k}: {v}\n")
    logging.info(f"Meta saved to {fn}")

def plot_data(raw, title="CONST1 Measurement"):
    # Parse values
    try:
        vals = [float(x) for x in raw.split(",")]
    except Exception as e:
        logging.error(f"Cannot parse data for plotting: {e}")
        return
    ch = np.arange(1, len(vals)+1)
    plt.figure()
    plt.plot(ch, vals, marker='o')
    plt.xlabel("Channel")
    plt.ylabel("Optical Power")
    plt.title(title)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.xticks(ch)
    plt.show()

def main():
    # Log system state at the start
    logging.info("=== System State ===")
    logging.info(f"Date and Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"Python Version: {platform.python_version()}")
    logging.info(f"PyVISA Version: {visa.__version__}")
    logging.info(f"Operating System: {platform.system()} {platform.release()}")
    logging.info(f"GPIB Address: {GPIB_ADDRESS}")
    logging.info("===================")

    p = argparse.ArgumentParser()
    subs = p.add_subparsers(dest="cmd", required=True)

    meas = subs.add_parser("measure")
    meas.add_argument("--unit", choices=["DBM", "W"], default="DBM",
                      help="Unit for measurement: DBM or W")
    meas.add_argument("--data-file", required=True, help="Path to save measurement data")
    meas.add_argument("--meta-file", default=None, help="Path to save instrument meta info")
    meas.add_argument("--plot", action="store_true", help="Plot the measurement results")

    args = p.parse_args()
    resource = GPIB_ADDRESS

    with MPM210H(resource) as mpm:
        if args.cmd == "measure":
            # Set desired unit
            mpm.send(f"UNIT {args.unit}")
            time.sleep(0.1)
            raw = perform_measurement(mpm)
            save_data(args.data_file, raw)
            if args.meta_file:
                save_meta(args.meta_file, query_meta(mpm))
            if args.plot:
                title = f"CONST1 Measurement ({args.unit})"
                plot_data(raw, title)

if __name__ == "__main__":
    main()