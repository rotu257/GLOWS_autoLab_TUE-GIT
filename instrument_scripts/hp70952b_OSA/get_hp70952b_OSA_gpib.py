#!/home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

import pyvisa
import numpy as np
import logging
import sys
import os
import time
import argparse
from tqdm import tqdm

# Initialize logging with a console handler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class OSAScanner:
    """Class to handle Optical Spectrum Analyzer (OSA) scanning operations."""
    
    def __init__(self, args=None):
        """Initialize with default parameters and command-line args."""
        self.rm = None
        self.inst = None
        self.args = args
        
        # Set default parameters
        self.gpib_addr = 23
        self.timeout_ms = 30000
        self.start_wl = 1400.0
        self.stop_wl = 1600.0
        self.points = 800
        self.filename = 'scan_data.txt'
        self.ref_level = -60.0
        self.sens = -70.0
        self.res_bw = 0.1

        # Override defaults with command-line arguments if provided
        if self.args:
            if self.args.gpib is not None:
                self.gpib_addr = self.args.gpib
            if self.args.timeout is not None:
                self.timeout_ms = self.args.timeout
            if self.args.start_wl is not None:
                self.start_wl = self.args.start_wl
            if self.args.stop_wl is not None:
                self.stop_wl = self.args.stop_wl
            if self.args.points is not None:
                self.points = self.args.points
            if self.args.filename is not None:
                self.filename = self.args.filename
            if self.args.ref_level is not None:
                self.ref_level = self.args.ref_level
            if self.args.sens is not None:
                self.sens = self.args.sens
            if self.args.res_bw is not None:
                self.res_bw = self.args.res_bw

        self.validate_params()

    def validate_params(self):
        """Validate configuration parameters."""
        try:
            if not (0 <= self.gpib_addr <= 30):
                raise ValueError("GPIB address must be between 0 and 30")
            if self.timeout_ms < 1000:
                raise ValueError("Timeout must be at least 1000 ms")
            if not (600 <= self.start_wl < self.stop_wl <= 1700):
                raise ValueError("Wavelength range must be 600-1700 nm, start < stop")
            if not (100 <= self.points <= 2000):
                raise ValueError("Points must be between 100 and 2000")
            if not (-90 <= self.ref_level <= 30):
                raise ValueError("Reference level must be between -90 and +30 dBm")
            if not (-90 <= self.sens <= -30):
                raise ValueError("Sensitivity must be between -90 and -30 dBm")
            if not (0.08 <= self.res_bw <= 10):
                raise ValueError("Resolution bandwidth must be between 0.08 and 10 nm")
        except ValueError as e:
            logger.error(f"Parameter validation error: {str(e)}")
            sys.exit(1)

    def connect_instrument(self):
        """Connect to the instrument."""
        try:
            self.rm = pyvisa.ResourceManager()
            self.inst = self.rm.open_resource(f'GPIB0::{self.gpib_addr}::INSTR')
            self.inst.timeout = self.timeout_ms
            self.inst.write_termination = '\n'
            self.inst.read_termination = '\n'
            logger.info(f"Connected to instrument at GPIB0::{self.gpib_addr}")
        except pyvisa.VisaIOError as e:
            logger.error(f"Failed to connect to instrument: {str(e)}")
            sys.exit(1)

    def query_instrument(self, query):
        """Query the instrument with a command."""
        try:
            result = self.inst.query(query)
            logger.info(f"Query '{query}' response: {result}")
            return result
        except pyvisa.VisaIOError as e:
            logger.error(f"Query failed: {str(e)}")
            sys.exit(1)

    def configure_instrument(self):
        """Configure the OSA for scanning."""
        try:
            self.inst.write(f'REMOTE {self.gpib_addr}')
            self.inst.clear()
            self.inst.write('IP')  # Instrument preset
            self.inst.write(f'STARTWL {self.start_wl}NM;STOPWL {self.stop_wl}NM;')
            self.inst.write(f'NPOINTS {self.points};')
            self.inst.write(f'RL {self.ref_level}DBM')  # Set reference level
            self.inst.write(f'SENS {self.sens}DBM')  # Set sensitivity
            self.inst.write(f'RB {self.res_bw}NM')  # Set resolution bandwidth
            self.inst.write('SNGLS;TS')
            logger.info("Instrument configured for scan")
        except pyvisa.VisaIOError as e:
            logger.error(f"Instrument configuration failed: {str(e)}")
            self.cleanup()
            sys.exit(1)

    def acquire_data(self):
        """Acquire and process scan data."""
        try:
            logger.info("Starting data acquisition...")
            with tqdm(total=100, desc="Scanning", unit="%") as pbar:
                raw = self.inst.query('TRA?')
                pbar.update(50)
                data = np.fromstring(raw, sep=',')
                pbar.update(50)
            
            if len(data) != self.points:
                logger.warning(f"Expected {self.points} points, got {len(data)}")
            
            return data
        except (pyvisa.VisaIOError, ValueError) as e:
            logger.error(f"Data acquisition failed: {str(e)}")
            self.cleanup()
            sys.exit(1)

    def save_data(self, data):
        """Save data to file and log parameters in the current working directory."""
        try:
            base, ext = os.path.splitext(self.filename)
            output_file = os.path.join(os.getcwd(), f"{base}{ext}")
            log_file = os.path.join(os.getcwd(), f"{base}.log")
            
            # Save configuration parameters to log file
            with open(log_file, 'w') as log_file_handle:
                log_file_handle.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file_handle.write(f"Sensitivity (dBm): {self.sens}\n")
                log_file_handle.write(f"Resolution Bandwidth (nm): {self.res_bw}\n")
                log_file_handle.write(f"Timeout (ms): {self.timeout_ms}\n")
                log_file_handle.write(f"Start Wavelength (nm): {self.start_wl}\n")
                log_file_handle.write(f"Stop Wavelength (nm): {self.stop_wl}\n")
                log_file_handle.write(f"Points: {self.points}\n")
                log_file_handle.write(f"Reference Level (dBm): {self.ref_level}\n")
                log_file_handle.write(f"Output Data File: {os.path.abspath(output_file)}\n")
            
            logger.info(f"Created log file: {log_file}")
            
            # Generate wavelength array
            wavelengths = np.linspace(self.start_wl, self.stop_wl, self.points)
            # Combine wavelengths and amplitudes
            output_data = np.column_stack((wavelengths, data))
            
            np.savetxt(
                output_file,
                output_data,
                fmt='%.6f',
                header='Wavelength (nm), Amplitude',
                comments='# '
            )
            
            # Verify file was created
            if not os.path.exists(output_file):
                raise IOError(f"File {output_file} was not created")
                
            logger.info(f"Saved {len(data)} points to {os.path.abspath(output_file)}")
            
        except IOError as e:
            logger.error(f"Failed to save data or log: {str(e)}")
            sys.exit(1)

    def cleanup(self):
        """Return to local control and close connections."""
        try:
            if self.inst:
                self.inst.write('LOCAL')
                self.inst.close()
            if self.rm:
                self.rm.close()
            logger.info("Instrument connection closed successfully")
        except pyvisa.VisaIOError as e:
            logger.error(f"Cleanup failed: {str(e)}")
        finally:
            self.inst = None
            self.rm = None

    def run(self):
        """Execute the complete scan process."""
        try:
            self.connect_instrument()
            if self.args and self.args.query:
                print(self.query_instrument(self.args.query))
                self.cleanup()
                sys.exit(0)
            self.configure_instrument()
            data = self.acquire_data()
            self.save_data(data)
            self.cleanup()
        except Exception as e:
            logger.error(f"Program failed: {str(e)}")
            self.cleanup()
            sys.exit(1)

def main():
    """Main function to run the OSA scanner."""
    parser = argparse.ArgumentParser(description="Optical Spectrum Analyzer (OSA) Scanner")
    parser.add_argument('-q', '--query', type=str, help="Query instrument (e.g., '*IDN?')")
    parser.add_argument('-f', '--filename', type=str, help="Output filename (default: scan_data.txt)")
    parser.add_argument('--start-wl', type=float, help="Start wavelength (nm, default: 1400)")
    parser.add_argument('--stop-wl', type=float, help="Stop wavelength (nm, default: 1600)")
    parser.add_argument('-p', '--points', type=int, help="Number of points (default: 800)")
    parser.add_argument('-g', '--gpib', type=int, help="GPIB address (default: 23)")
    parser.add_argument('-t', '--timeout', type=int, help="Timeout (ms, default: 5000)")
    parser.add_argument('--ref-level', type=float, help="Reference level (dBm, default: -60)")
    parser.add_argument('--sens', type=float, help="Sensitivity (dBm, default: -70)")
    parser.add_argument('--res-bw', type=float, help="Resolution bandwidth (nm, default: 0.1)")

    args = parser.parse_args()

    try:
        logger.info(f"Current working directory: {os.getcwd()}")
        scanner = OSAScanner(args=args)
        scanner.run()
    except Exception as e:
        logger.error(f"Program failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()


    """
Command-line usage for osa_scanner.py:

  python get_hp70952b_OSA_gpib.py [options]

Options:
  -q, --query <string>      Query the instrument with a specific command (e.g., '*IDN?'). If provided, only the query is executed, and the program exits.
  -f, --filename <string>   Output filename for scan data (default: scan_data.txt). Saved in the current working directory.
  --start-wl <float>        Start wavelength in nm (default: 1400). Must be between 600 and 1700 nm, less than stop-wl.
  --stop-wl <float>         Stop wavelength in nm (default: 1600). Must be between 600 and 1700 nm, greater than start-wl.
  -p, --points <int>        Number of points in the scan (default: 800). Must be between 100 and 2000.
  -g, --gpib <int>          GPIB address of the instrument (default: 23). Must be between 0 and 30.
  -t, --timeout <int>       Timeout in milliseconds (default: 30000). Minimum 1000 ms. Actual timeout may be increased based on points (50 ms per point).
  --ref-level <float>       Reference level in dBm (default: -60). Must be between -90 and +30 dBm.
  --sens <float>            Sensitivity in dBm (default: -70). Must be between -90 and -30 dBm.
  --res-bw <float>          Resolution bandwidth in nm (default: 0.1). Must be between 0.08 and 10 nm.

Examples:
  Run with default settings:
    python osa_scanner.py
  Query instrument identity:
    python osa_scanner.py -q "*IDN?"
  Custom scan parameters:
    get_hp70952b_OSA_gpib.py --start-wl 1300 --stop-wl 1500 -p 800 --sens -65 --res-bw 0.2 -f custom_scan.txt
"""