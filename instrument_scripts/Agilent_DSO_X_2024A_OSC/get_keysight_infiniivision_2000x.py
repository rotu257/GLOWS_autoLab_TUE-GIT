#!/home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

import argparse
import logging
import sys
import time
import json
from typing import List, Optional
import pyvisa
import numpy as np
from pydantic import BaseModel, ValidationError, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Default resource string
DEFAULT_RESOURCE = 'USB0::2391::6038::MY54231340::INSTR'

class OscilloscopeConfig(BaseModel):
    """Configuration model for oscilloscope settings."""
    channels: List[str] = Field(default=['CHAN1'], description="List of channels to acquire from")
    resource: str = Field(default=DEFAULT_RESOURCE, description="Oscilloscope VISA resource string")
    filename: Optional[str] = Field(default=None, description="Output file prefix for waveform data")
    force: bool = Field(default=False, description="Allow overwriting existing files")
    timeout: float = Field(default=10.0, gt=0, description="Timeout in seconds for acquisition")
    autoset: bool = Field(default=False, description="Enable autoset during initialization")

    def save_to_file(self, config_file: str) -> None:
        """Save configuration to a JSON file."""
        try:
            with open(config_file, 'w') as f:
                json.dump(self.dict(), f, indent=2)
            logger.info(f"Configuration saved to {config_file}")
        except IOError as e:
            logger.error(f"Failed to save configuration to {config_file}: {e}")
            raise

    @classmethod
    def load_from_file(cls, config_file: str) -> 'OscilloscopeConfig':
        """Load configuration from a JSON file."""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            config = cls(**config_data)
            logger.info(f"Configuration loaded from {config_file}")
            return config
        except (IOError, json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to load configuration from {config_file}: {e}")
            raise

class KeysightInfiniiVision2000X:
    """Class to control a Keysight InfiniiVision 2000 X-Series oscilloscope."""
    
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
            self.scope = self.rm.open_resource(self.config.resource)
            self.scope.timeout = int(self.config.timeout * 1000)  # Convert to milliseconds
            logger.info("Querying instrument ID...")
            idn = self.query('*IDN?').strip()
            logger.info(f"Instrument ID: {idn}")
        except pyvisa.VisaIOError as e:
            logger.error(f"Failed to connect to oscilloscope at {self.config.resource}: {e}")
            raise

    def _set_channels(self) -> None:
        """Validate and set channels, defaulting to CHAN1 if none specified."""
        if not self.config.channels:
            self.config.channels = ['CHAN1']
            logger.info("No channels specified; defaulting to CHAN1.")
        else:
            for ch in self.config.channels:
                if ch not in [f'CHAN{i}' for i in range(1, 5)]:
                    logger.error(f"Invalid channel: {ch}. Use CHAN1, CHAN2, CHAN3, or CHAN4.")
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
        self.write(':AUToscale')
        while self.query('*OPC?').strip() != '1':
            time.sleep(0.05)
        logger.info("Autoset complete.")

    def run(self) -> None:
        """Start acquisition."""
        logger.info("Starting acquisition...")
        self.write(':RUN')

    def stop(self) -> None:
        """Stop acquisition."""
        logger.info("Stopping acquisition...")
        self.write(':STOP')

    def get_waveform(self, channel: str) -> str:
        """Retrieve waveform data from the specified channel in ASCII format."""
        logger.info(f"Acquiring waveform from {channel}...")
        self.write(f':WAVeform:SOURce {channel}')
        self.write(':WAVeform:FORMat ASCii')
        try:
            data = self.scope.query(':WAVeform:DATA?').strip()
            logger.info(f"Retrieved {len(data.split(','))} samples from {channel}")
            return data
        except pyvisa.VisaIOError as e:
            logger.error(f"Failed to acquire waveform from {channel}: {e}")
            raise

    def get_preamble(self, channel: str) -> str:
        """Retrieve the entire waveform preamble."""
        logger.info(f"Retrieving preamble for {channel}...")
        self.write(f':WAVeform:SOURce {channel}')
        preamble = self.query(':WAVeform:PREamble?').strip()
        logger.debug(f"Raw preamble: {preamble}")
        return preamble

    def save_waveform(self, channel: str, data: str, preamble: str) -> None:
        """Save waveform data and preamble to files."""
        if not self.config.filename:
            logger.warning("No filename provided; skipping save.")
            return
        
        base_filename = f"{self.config.filename}_keysight_{channel.lower()}"
        data_filename = f"{base_filename}.txt"
        log_filename = f"{base_filename}.log"

        import os
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
        
        self.write(':ACQuire:TYPE HRESolution')
        
        preambles = {}
        for channel in self.config.channels:
            preambles[channel] = self.get_preamble(channel)
        
        logger.info("Setting trigger sweep to AUTO...")
        self.write(':TRIGger:SWEep AUTO')
        
        # Force trigger to ensure acquisition readiness
        logger.info("Forcing trigger to prepare for acquisition...")
        self.write(':TRIGger:FORCe')
        time.sleep(0.5)  # Brief delay after force trigger
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                digitize_cmd = ':DIGitize ' + ','.join(self.config.channels)
                self.write(digitize_cmd)
                while self.query('*OPC?').strip() != '1':
                    time.sleep(0.05)
                break
            except pyvisa.VisaIOError as e:
                logger.warning(f"Acquisition attempt {attempt + 1}/{max_attempts} failed: {e}")
                if attempt == max_attempts - 1:
                    logger.error("Acquisition failed after all attempts.")
                    raise
                time.sleep(1.0)
        
        for channel in self.config.channels:
            data = self.get_waveform(channel)
            logger.info(f"Waveform length for {channel}: {len(data.split(','))} samples")
            if self.config.filename:
                self.save_waveform(channel, data, preambles[channel])
        
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
        description="Acquire waveforms from a Keysight InfiniiVision 2000 X-Series oscilloscope.",
        epilog="Example: %(prog)s -c CHAN1,CHAN2 -f waveform --force --autoset --config-save config.json"
    )
    parser.add_argument(
        '-c', '--channels',
        type=str,
        default='CHAN1',
        help='Comma-separated list of channels (e.g., CHAN1,CHAN2). Defaults to CHAN1.'
    )
    parser.add_argument(
        '-r', '--resource',
        type=str,
        default=DEFAULT_RESOURCE,
        help=f'Oscilloscope VISA resource string (default: {DEFAULT_RESOURCE})'
    )
    parser.add_argument(
        '-f', '--filename',
        type=str,
        default=None,
        help='Output file prefix for waveform data (e.g., "waveform" creates waveform_keysight_chan1.txt)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Allow overwriting existing files'
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=10.0,
        help='Timeout in seconds for acquisition (default: 10.0)'
    )
    parser.add_argument(
        '--autoset',
        action='store_true',
        help='Enable autoset to automatically configure channel and trigger settings'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset oscilloscope to preset state before acquisition'
    )
    parser.add_argument(
        '--config-save',
        type=str,
        default=None,
        help='Save configuration to specified JSON file'
    )
    parser.add_argument(
        '--config-load',
        type=str,
        default=None,
        help='Load configuration from specified JSON file'
    )
    return parser.parse_args()

def main() -> None:
    """Main function to run the script."""
    args = parse_arguments()
    
    if args.config_load:
        try:
            config = OscilloscopeConfig.load_from_file(args.config_load)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    else:
        channels = [ch.strip() for ch in args.channels.split(',') if ch.strip()]
        try:
            config = OscilloscopeConfig(
                channels=channels,
                resource=args.resource,
                filename=args.filename,
                force=args.force,
                timeout=args.timeout,
                autoset=args.autoset
            )
        except ValidationError as e:
            logger.error(f"Invalid configuration: {e}")
            sys.exit(1)
    
    if args.config_save:
        try:
            config.save_to_file(args.config_save)
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            sys.exit(1)
    
    scope = None
    try:
        scope = KeysightInfiniiVision2000X(config)
        if args.reset:
            scope.reset()
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
# Your command (now without errors)
python3 get_keysight_infiniivision_2000x.py -c CHAN1,CHAN4 -f waveform --force

# With autoset and reset
python3 get_keysight_infiniivision_2000x.py -c CHAN1,CHAN4 -f waveform --force --autoset

# Save/load config
python3 get_keysight_infiniivision_2000x.py -c CHAN1,CHAN4 -f waveform --force --config-save config.json
python3 get_keysight_infiniivision_2000x.py --config-load config.json

# Save configuration to a JSON file
python3 get_keysight_infiniivision_2000x.py -c CHAN1,CHAN2 -f waveform --force --autoset --config-save config.json

# Load configuration from a JSON file
python3 get_keysight_infiniivision_2000x.py --config-load config.json

# Use autoset and acquire from CHAN1, CHAN2
python3 get_keysight_infiniivision_2000x.py -c CHAN1,CHAN2 -f waveform --force --autoset

# Specify different resource and timeout
python3 get_keysight_infiniivision_2000x.py -c CHAN1 -f waveform --force --autoset -r USB0::2391::6038::MY54231340::INSTR
    
    '''