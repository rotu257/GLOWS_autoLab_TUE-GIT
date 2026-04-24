#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

import matplotlib.pyplot as plt
import numpy as np
import os
import time
import argparse

def read_measurement_files(folder_path, num_files=201):
    """
    Read measurement values from files named measurement_file1_PM400 to measurement_file201_PM400.
    Returns lists of valid x and y values, skipping negatives and invalid data.
    """
    x_values = np.arange(0.0, 0.401, 0.002)  # 0.0 to 0.4 with step 0.002 (201 points)
    y_values = []
    valid_indices = []
    invalid_data_log = []

    for i in range(1, num_files + 1):
        filename = f"measurement_file{i}_PM400"
        file_path = os.path.join(folder_path, filename)
        try:
            with open(file_path, 'r') as f:
                data = f.read().strip()
                try:
                    value = float(data)
                    if value >= 0:  # Only include non-negative values
                        y_values.append(value)
                        valid_indices.append(i - 1)  # Store index for x-value
                    else:
                        invalid_data_log.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {filename}: Negative value ({value})")
                except ValueError:
                    invalid_data_log.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {filename}: Invalid data ({data})")
        except FileNotFoundError:
            invalid_data_log.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {filename}: File not found")
        except Exception as e:
            invalid_data_log.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {filename}: Error ({str(e)})")

    # Filter x_values to match valid y_values
    x_valid = [x_values[i] for i in valid_indices]

    # Log invalid data
    if invalid_data_log:
        with open('invalid_measurements_plot.log', 'w') as f:
            f.write("\n".join(invalid_data_log))
        print(f"Logged {len(invalid_data_log)} invalid measurements to invalid_measurements_plot.log")

    return x_valid, y_values

def mw_to_dbm(power_mw):
    """
    Convert power from mW to dBm.
    Input power_mw is in watts, so multiply by 1000 to convert to mW.
    """
    power_mw = np.array(power_mw) * 1000  # Convert watts to mW
    # Avoid log10(0) by replacing 0 with a small value
    power_mw = np.where(power_mw <= 0, 1e-10, power_mw)
    return 10 * np.log10(power_mw)

def plot_measurements(x_values, y_values, scale='mW'):
    """
    Create a scatter plot of measurement values in mW or dBm and save as PNG.
    scale: 'mW' or 'dBm' to specify the y-axis scale.
    """
    plt.figure(figsize=(10, 6))
    
    if scale.lower() == 'dbm':
        y_values_converted = mw_to_dbm(y_values)
        ylabel = 'Power (dBm)'
        filename = 'power_measurements_dbm.png'
    else:
        y_values_converted = np.array(y_values) * 1000  # Convert watts to mW
        ylabel = 'Power (mW)'
        filename = 'power_measurements_mw.png'

    plt.scatter(x_values, y_values_converted, color='blue', s=10, label='Power Measurements')
    plt.title(f'Power Measurements from PM400 Files ({scale})')
    plt.xlabel('Index (0.0 to 0.4)')
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.legend()
    plt.xlim(0.0, 0.4)
    plt.show()
    plt.savefig(filename)
    print(f"Plot saved as {filename}")
    plt.close()

if __name__ == '__main__':
    # Set up argument parser for scale selection
    parser = argparse.ArgumentParser(description='Plot power measurements in mW or dBm.')
    parser.add_argument('--scale', choices=['mW', 'dBm'], default='mW', 
                        help='Scale for y-axis: mW or dBm (default: mW)')
    args = parser.parse_args()

    # Specify the folder containing the measurement files
    folder_path = "/home/user_rotu/Desktop/L_I_curve/test1/"  # Change to your folder path if needed
    x_vals, y_vals = read_measurement_files(folder_path)
    if y_vals:  # Only plot if there are valid measurements
        plot_measurements(x_vals, y_vals, scale=args.scale)
    else:
        print("No valid measurements found to plot.")