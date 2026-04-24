#!/home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
import argparse
import logging
import sys
import time
from typing import List, Optional
import pyvisa
import numpy as np
from pydantic import BaseModel, ValidationError, Field
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Default IP address
DEFAULT_IP = '192.168.1.10'

class OscilloscopeConfig(BaseModel):
    """Configuration model for oscilloscope settings."""
    channels: List[str] = Field(default=['CH1'], description="List of channels to acquire from")
    ip_address: str = Field(default=DEFAULT_IP, description="Oscilloscope IP address")
    filename: Optional[str] = Field(default=None, description="Output file prefix for waveform data")
    force: bool = Field(default=False, description="Allow overwriting existing files")
    timeout: float = Field(default=20.0, gt=0, description="Timeout in seconds for acquisition")
    autoset: bool = Field(default=False, description="Enable autoset during initialization")
    acq_mode: str = Field(
        default='sample',
        description="Acquisition mode: sample, hires, average, peakdetect"
    )
    num_avg: int = Field(
        default=16,
        ge=2, le=65536,
        description="Number of averages when acq_mode=average (2..65536)"
    )

class TektronixDPO72304DX:
    """Class to control a Tektronix DPO72304DX oscilloscope."""

    def __init__(self, config: OscilloscopeConfig):
        """Initialize the oscilloscope with given configuration."""
        self.config = config
        self.rm = pyvisa.ResourceManager('@py')
        self.scope = None
        self._connect()
        self._set_channels()

    def _connect(self) -> None:
        """Establish connection to the oscilloscope."""
        try:
            resource = f'TCPIP0::{self.config.ip_address}::INSTR'
            self.scope = self.rm.open_resource(resource)
            self.scope.timeout = int(self.config.timeout * 1000)  # Convert to milliseconds
            logger.info("Querying instrument ID...")
            idn = self.query('*IDN?').strip()
            logger.info(f"Instrument ID: {idn}")
        except pyvisa.VisaIOError as e:
            logger.error(f"Failed to connect to oscilloscope at {self.config.ip_address}: {e}")
            raise

    def _set_channels(self) -> None:
        """Validate and set channels, defaulting to CH1 if none specified."""
        if not self.config.channels:
            self.config.channels = ['CH1']
            logger.info("No channels specified; defaulting to CH1.")
        else:
            # Validate user-specified channels
            valid_channels = [f'CH{i}' for i in range(1, 5)]
            for ch in self.config.channels:
                if ch not in valid_channels:
                    logger.error(f"Invalid channel: {ch}. Use CH1, CH2, CH3, or CH4.")
                    raise ValueError(f"Invalid channel: {ch}")
            logger.info(f"Using specified channels: {self.config.channels}")

    def query(self, command: str) -> str:
        """Send a query and return the response."""
        try:
            return self.scope.query(command)
        except pyvisa.VisaIOError as e:
            logger.error(f"Query '{command}' failed: {e}")
            raise

    def write(self, command: str) -> None:
        """Send a command to the oscilloscope."""
        try:
            self.scope.write(command)
        except pyvisa.VisaIOError as e:
            logger.error(f"Command '{command}' failed: {e}")
            raise

    def reset(self) -> None:
        """Reset the oscilloscope and wait for operation completion."""
        logger.info("Resetting oscilloscope...")
        self.write('*RST')
        while self.query('*OPC?').strip() != '1':
            time.sleep(0.05)
        logger.info("Reset complete.")

    def autoset(self) -> None:
        """Execute autoset to optimize settings for active channels."""
        logger.info("Executing autoset...")
        self.write(':AUTOSet EXECute')
        while self.query('*OPC?').strip() != '1':
            time.sleep(0.05)
        logger.info("Autoset complete.")

    def check_trigger_state(self, max_attempts: int = 3, delay: float = 1.0) -> bool:
        """Check if the trigger is firing."""
        for attempt in range(max_attempts):
            state = self.query(':TRIGger:STATe?').strip()
            logger.debug(f"Trigger state: {state}")
            if state in ['TRIGGER', 'READY']:
                return True
            logger.warning(f"Trigger not firing (state: {state}), attempt {attempt + 1}/{max_attempts}")
            time.sleep(delay)
        return False

    def run(self) -> None:
        """Start acquisition."""
        logger.info("Starting acquisition...")
        self.write(':ACQuire:STATe ON')

    def stop(self) -> None:
        """Stop acquisition."""
        logger.info("Stopping acquisition...")
        self.write(':ACQuire:STATe OFF')

    def get_waveform(self, channel: str) -> str:
        """Retrieve waveform data from the specified channel in ASCII format."""
        logger.info(f"Acquiring waveform from {channel}...")
        self.write(f':DATA:SOUrce {channel}')
        self.write(':DATA:ENCdg ASCii')  # ASCII format (voltages in volts)
        try:
            data = self.scope.query(':CURVe?').strip()
            logger.info(f"Retrieved {len(data.split(','))} samples from {channel}")
            return data
        except pyvisa.VisaIOError as e:
            logger.error(f"Failed to acquire waveform from {channel}: {e}")
            raise

    def get_preamble(self, channel: str) -> str:
        """Retrieve the entire waveform preamble."""
        logger.info(f"Retrieving preamble for {channel}...")
        preamble = self.query(':WFMOutpre?').strip()
        logger.debug(f"Raw preamble: {preamble}")
        return preamble

    def save_waveform(self, channel: str, data: str, preamble: str) -> None:
        """Save waveform data and preamble to files."""
        if not self.config.filename:
            logger.warning("No filename provided; skipping save.")
            return

        base_filename = f"{self.config.filename}_tek_{channel.lower()}"
        data_filename = f"{base_filename}.txt"
        log_filename = f"{base_filename}.log"

        if not self.config.force and (os.path.exists(data_filename) or os.path.exists(log_filename)):
            logger.error(f"File(s) {data_filename} or {log_filename} already exist. Use --force to overwrite.")
            raise FileExistsError(f"File(s) {data_filename} or {log_filename} already exist.")

        try:
            with open(data_filename, 'w') as f:
                f.write(data)
            logger.info(f"Saved waveform data to {data_filename}")
        except IOError as e:
            logger.error(f"Failed to save waveform data to {data_filename}: {e}")
            raise

        try:
            with open(log_filename, 'w') as f:
                f.write(preamble)
            logger.info(f"Saved preamble to {log_filename}")
        except IOError as e:
            logger.error(f"Failed to save preamble to {log_filename}: {e}")
            raise

    def acquire_and_save(self) -> None:
        """Acquire and save waveforms for all configured channels."""
        if not self.config.filename:
            logger.info("No filename provided; acquiring waveforms without saving.")

        self.run()  # Ensure acquisition is running

        # Retrieve preamble for all channels first
        preambles = {}
        for channel in self.config.channels:
            preambles[channel] = self.get_preamble(channel)

        # Set acquisition mode
        mode_map = {
            'sample':     'SAMple',
            'hires':      'HIRes',
            'average':    'AVErage',
            'peakdetect': 'PEAKdetect',
        }

        requested_mode = self.config.acq_mode.lower()
        if requested_mode not in mode_map:
            raise ValueError(
                f"Unsupported acquisition mode: {self.config.acq_mode}. "
                f"Supported: {', '.join(mode_map.keys())}"
            )

        scpi_mode = mode_map[requested_mode]
        logger.info(f"Setting acquisition mode to {requested_mode.upper()} ({scpi_mode})")
        self.write(f':ACQuire:MODe {scpi_mode}')

        if requested_mode == 'average':
            logger.info(f"Setting number of averages to {self.config.num_avg}")
            self.write(f':ACQuire:NUMAVg {self.config.num_avg}')

        self.write(':ACQuire:STOPAfter SEQuence')

        # Set trigger mode to AUTO
        logger.info("Setting trigger mode to AUTO...")
        self.write(':TRIGger:A:MODe AUTO')

        # Check and fire trigger
        if not self.check_trigger_state():
            logger.warning("Trigger not firing; forcing trigger.")
            self.write(':TRIGger:FORCe')

        # Retry acquisition up to 3 times
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                self.write(':TRIGger:FORCe')  # Fire trigger before stopping
                while self.query('*OPC?').strip() != '1':
                    time.sleep(0.05)
                self.stop()  # Stop acquisition after trigger
                break
            except pyvisa.VisaIOError as e:
                logger.warning(f"Acquisition attempt {attempt + 1}/{max_attempts} failed: {e}")
                if attempt == max_attempts - 1:
                    logger.error("Acquisition failed after all attempts.")
                    raise
                time.sleep(1.0)

        # Acquire waveforms
        for channel in self.config.channels:
            data = self.get_waveform(channel)
            logger.info(f"Waveform length for {channel}: {len(data.split(','))} samples")
            if self.config.filename:
                self.save_waveform(channel, data, preambles[channel])

        # Return to run mode after acquisition
        self.run()

    def setup(self) -> None:
        """Perform oscilloscope setup and acquisition."""
        if self.config.autoset:
            self.autoset()
        self.acquire_and_save()

    def close(self) -> None:
        """Close the connection to the oscilloscope."""
        if self.scope:
            self.scope.close()
        self.rm.close()
        logger.info("Connection closed.")

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Acquire waveforms from a Tektronix DPO72304DX oscilloscope.",
        epilog="Examples:\n"
               "  %(prog)s -f wave --force\n"
               "  %(prog)s -c CH1,CH2 -f wave_hires --acq-mode hires --force\n"
               "  %(prog)s -f wave_avg --acq-mode average --num-avg 64 --force"
    )
    parser.add_argument(
        '-c', '--channels',
        type=str,
        default='CH1',
        help='Comma-separated list of channels (e.g., CH1,CH2). Defaults to CH1.'
    )
    parser.add_argument(
        '-i', '--ip-address',
        type=str,
        default=DEFAULT_IP,
        help=f'Oscilloscope IP address (default: {DEFAULT_IP})'
    )
    parser.add_argument(
        '-f', '--filename',
        type=str,
        default=None,
        help='Output file prefix for waveform data (e.g. "wave" → wave_tek_ch1.txt)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Allow overwriting existing files'
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=20.0,
        help='Timeout in seconds for acquisition (default: 20.0)'
    )
    parser.add_argument(
        '--autoset',
        action='store_true',
        help='Enable autoset to automatically configure channel and trigger settings'
    )
    parser.add_argument(
        '--acq-mode',
        type=str.lower,
        default='sample',
        choices=['sample', 'hires', 'average', 'peakdetect'],
        help='Acquisition mode (default: sample)'
    )
    parser.add_argument(
        '--num-avg',
        type=int,
        default=16,
        help='Number of averages when --acq-mode=average (default: 16)'
    )

    return parser.parse_args()

def main() -> None:
    """Main function to run the script."""
    args = parse_arguments()

    # Convert channels string to list
    channels = [ch.strip() for ch in args.channels.split(',') if ch.strip()]

    # Create configuration
    try:
        config = OscilloscopeConfig(
            channels=channels,
            ip_address=args.ip_address,
            filename=args.filename,
            force=args.force,
            timeout=args.timeout,
            autoset=args.autoset,
            acq_mode=args.acq_mode,
            num_avg=args.num_avg
        )
    except ValidationError as e:
        logger.error(f"Invalid configuration: {e}")
        sys.exit(1)

    scope = None
    try:
        scope = TektronixDPO72304DX(config)
        scope.setup()
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)
    finally:
        if scope:
            scope.close()

if __name__ == '__main__':
    main()


'''
# Classic sample mode (default)
python get_Tektronix_DPO72304DX_oscilloscope_ASCII.py -f wave --force

# High resolution mode – better vertical resolution, lower effective bandwidth
python get_Tektronix_DPO72304DX_oscilloscope_ASCII.py -f wave_hires --force --acq-mode hires

# Averaging (16 waveforms by default)
python get_Tektronix_DPO72304DX_oscilloscope_ASCII.py -f wave_avg --force --acq-mode average --num-avg 32
'''
