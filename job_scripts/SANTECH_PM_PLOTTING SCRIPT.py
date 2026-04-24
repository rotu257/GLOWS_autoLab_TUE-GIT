import matplotlib.pyplot as plt
import numpy as np
import os

# Function to convert dBm to mW (not used for plotting, but included for completeness)
def dbm_to_mw(dbm):
    return 10 ** (dbm / 10)

# Function to read data from files
def read_data(num_files, file_prefix="mpm210H_measurement_data_"):
    currents = np.linspace(0, 0.4, num_files)  # Current values from 0 to 0.4 A
    port_data = {1: [], 2: [], 3: [], 4: []}  # Dictionary to store data for each port
    
    for i in range(num_files):
        filename = f"{file_prefix}{i}"
        try:
            with open(filename, 'r') as f:
                data = f.readline().strip().split(',')
                if len(data) != 4:
                    print(f"Warning: File {filename} does not contain exactly 4 values")
                    continue
                for port in range(4):
                    try:
                        port_data[port + 1].append(float(data[port]))
                    except ValueError:
                        print(f"Warning: Invalid data in file {filename} for port {port + 1}")
                        port_data[port + 1].append(np.nan)
        except FileNotFoundError:
            print(f"Warning: File {filename} not found")
            for port in range(4):
                port_data[port + 1].append(np.nan)
    
    return currents, port_data

# Function to plot data for selected ports
def plot_ports(currents, port_data, ports_to_plot):
    plt.figure(figsize=(10, 6))
    
    for port in ports_to_plot:
        if port in port_data:
            plt.plot(currents, port_data[port], label=f'Port {port}', marker='o', markersize=4)
        else:
            print(f"Warning: Port {port} not found in data")
    
    plt.xlabel('Current (A)')
    plt.ylabel('Power (dBm)')
    plt.title('Power Meter Measurements vs Current')
    plt.grid(True)
    plt.legend()
    plt.savefig('power_meter_plot.png')
    plt.close()

# Main execution
if __name__ == "__main__":
    # Read data from 201 files
    currents, port_data = read_data(201)
    
    # Allow user to choose ports (1, 2, 3, 4 or combinations)
    print("Available ports: 1, 2, 3, 4")
    user_input = input("Enter ports to plot (e.g., '1,2,3' or 'all' for all ports): ")
    
    if user_input.lower() == 'all':
        ports_to_plot = [1, 2, 3, 4]
    else:
        try:
            ports_to_plot = [int(p) for p in user_input.split(',') if int(p) in [1, 2, 3, 4]]
            if not ports_to_plot:
                print("No valid ports selected. Plotting all ports.")
                ports_to_plot = [1, 2, 3, 4]
        except ValueError:
            print("Invalid input. Plotting all ports.")
            ports_to_plot = [1, 2, 3, 4]
    
    # Plot the selected ports
    plot_ports(currents, port_data, ports_to_plot)
    print("Plot saved as 'power_meter_plot.png'")