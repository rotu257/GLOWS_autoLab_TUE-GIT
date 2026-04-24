#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

import numpy as np
import matplotlib.pyplot as plt
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def read_preamble(log_filename: str) -> dict:
    """Read and parse the preamble from the .log file."""
    try:
        with open(log_filename, 'r') as f:
            preamble = f.read().strip()
        params = preamble.split(';')
        
        # Extract key parameters
        preamble_dict = {}
        try:
            preamble_dict['YMULT'] = float(params[params.index('YOFF') - 2])  # Vertical gain (volts/LSB)
            preamble_dict['YOFF'] = float(params[params.index('YOFF')])  # Vertical offset (volts)
            preamble_dict['XINCR'] = float(params[params.index('XINCR')])  # Time increment (seconds)
            preamble_dict['XZERO'] = float(params[params.index('XZERO')])  # Time at first sample (seconds)
            preamble_dict['NR_PT'] = int(params[params.index('NR_PT')])  # Number of points
        except (IndexError, ValueError) as e:
            logger.error(f"Failed to parse preamble from {log_filename}: {e}")
            raise
        logger.info(f"Preamble parameters: {preamble_dict}")
        return preamble_dict
    except IOError as e:
        logger.error(f"Failed to read {log_filename}: {e}")
        raise

def read_waveform(bin_filename: str) -> np.ndarray:
    """Read the waveform data from the .bin file."""
    try:
        data = np.fromfile(bin_filename, dtype=np.int8)
        logger.info(f"Read {len(data)} samples from {bin_filename}")
        return data
    except IOError as e:
        logger.error(f"Failed to read {bin_filename}: {e}")
        raise

def reconstruct_waveform(data: np.ndarray, preamble: dict) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct the waveform in volts and time."""
    # Convert raw data to volts
    voltages = data * preamble['YMULT'] + preamble['YOFF']
    
    # Generate time axis
    n_points = preamble['NR_PT']
    times = preamble['XZERO'] + np.arange(n_points) * preamble['XINCR']
    
    # Verify data length
    if len(data) != n_points:
        logger.warning(f"Data length ({len(data)}) does not match preamble NR_PT ({n_points})")
    
    return times, voltages

def plot_waveform(times: np.ndarray, voltages: np.ndarray, channel: str, output_file: str = None):
    """Plot the waveform and optionally save to file."""
    plt.figure(figsize=(10, 6))
    plt.plot(times * 1e9, voltages * 1e3, label=f'Channel {channel}')  # Time in ns, voltage in mV
    plt.xlabel('Time (ns)')
    plt.ylabel('Voltage (mV)')
    plt.title(f'Waveform from Channel {channel}')
    plt.grid(True)
    plt.legend()
    
    if output_file:
        plt.savefig(output_file)
        logger.info(f"Saved plot to {output_file}")
    plt.show()

def main(bin_filename: str, log_filename: str, channel: str, plot_file: str = None):
    """Main function to reconstruct and plot the waveform."""
    try:
        # Read files
        preamble = read_preamble(log_filename)
        data = read_waveform(bin_filename)
        
        # Reconstruct waveform
        times, voltages = reconstruct_waveform(data, preamble)
        
        # Plot waveform
        plot_waveform(times, voltages, channel, plot_file)
        
    except Exception as e:
        logger.error(f"Reconstruction failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Reconstruct and plot a waveform from Tektronix DPO72304DX oscilloscope files.",
        epilog="Example: %(prog)s waveform_tek_ch1.bin waveform_tek_ch1.log CH1 --plot waveform_ch1.png"
    )
    parser.add_argument(
        'bin_file',
        type=str,
        help='Binary waveform file (e.g., waveform_tek_ch1.bin)'
    )
    parser.add_argument(
        'log_file',
        type=str,
        help='Preamble log file (e.g., waveform_tek_ch1.log)'
    )
    parser.add_argument(
        'channel',
        type=str,
        help='Channel name (e.g., CH1)'
    )
    parser.add_argument(
        '--plot',
        type=str,
        default=None,
        help='Output file for the plot (e.g., waveform_ch1.png)'
    )
    
    args = parser.parse_args()
    main(args.bin_file, args.log_file, args.channel, args.plot)