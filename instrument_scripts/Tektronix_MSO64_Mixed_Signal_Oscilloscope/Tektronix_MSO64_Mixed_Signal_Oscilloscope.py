#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
import pyvisa as visa
import numpy as np
import matplotlib.pyplot as plt
import time
import argparse

# Argument parser
parser = argparse.ArgumentParser(description='Oscilloscope Data Acquisition')
parser.add_argument('filename', type=str, help='filename to save the waveform data')
parser.add_argument('-c', '--channel', type=int, default=2, choices=[1, 2],
                    help='choose the channel (1 or 2)')
parser.add_argument('-p', '--plot', action='store_true', help='plot the waveform')
parser.add_argument('-l', '--cursor', type=float, help='cursor location value')

# Parse the arguments
args = parser.parse_args()

# Specify the oscilloscope address
oscilloscope_address = "TCPIP::192.168.1.10::INSTR"

# Connect to the oscilloscope
resource_manager = visa.ResourceManager()
oscilloscope = resource_manager.open_resource(oscilloscope_address, timeout=10000)  # Set timeout value in milliseconds
print("Connected to: " + oscilloscope.query("*IDN?"))

# Configure the oscilloscope
oscilloscope.write(f'DATA:SOURCE CH{args.channel}')
oscilloscope.write(f'DISPLAY:WAVEVIEW1:CH{args.channel}:STATE 1')

time.sleep(2)

oscilloscope.write('DATa:ENCdg ASCII')
oscilloscope.write('DATa:WIDTH 2')
#oscilloscope.write('HORIZONTAL:RECORDLENGTH 1000')
oscilloscope.write('HORIZONTAL:SCALE 20e-3')  # sets the horizontal scale to 20 ns/division.
oscilloscope.write('DATA SNAP')

time.sleep(2)

oscilloscope.write('ACQUIRE:MODE SAMPLE')
oscilloscope.write('ACQUIRE:STATE ON')
oscilloscope.write('ACQUIRE:STATE STOP')  # STOPS acquisitions of waveform data and resets the count of the number of acquisitions.

time.sleep(2)

# Getting axis info
oscilloscope.query('*OPC?')
ymult = float(oscilloscope.query('WFMOutpre:YMULT?'))
yzero = float(oscilloscope.query('WFMOutpre:YZERO?'))
yoff = float(oscilloscope.query('WFMOutpre:YOFF?'))
xincr = float(oscilloscope.query('WFMOutpre:XINCR?'))

# Wait until the acquisition is complete before taking the measurement
oscilloscope.write('*OPC?')

# Reading ASCII Data from the instrument
waveform_data = oscilloscope.query('CURVE?')
oscilloscope.query('*ESR?')

time.sleep(2)

# Convert ASCII data to numeric values
waveform_values = np.array(waveform_data.strip().split(','), dtype=np.float32)
Volts = (waveform_values - yoff) * ymult + yzero

# Calculate time axis based on cursor location
if args.cursor:
    cursor_pos = args.cursor
    time_vals = np.arange(-cursor_pos * xincr, (len(Volts) - cursor_pos) * xincr, xincr)
else:
    time_vals = np.arange(0, xincr * len(Volts), xincr)[:len(Volts)]

# Save waveform data to a file
np.savetxt(args.filename, np.column_stack((time_vals, Volts)), delimiter='\t', header="Time\tVoltage", comments='')

# Plot the waveform if requested
if args.plot:
    plt.plot(time_vals, Volts)
    plt.xlabel('Time')
    plt.ylabel('Voltage')
    plt.show()

oscilloscope.write('ACQUIRE:STATE RUN')  # starts the acquisition of waveform data and resets the count of the number of acquisitions.
oscilloscope.write('CLEAR')

# Disconnect from the oscilloscope
oscilloscope.close()
resource_manager.close()
print("Disconnected from the oscilloscope.")


'''

Usage : 

python script.py data.txt -c 1 -p -l 50e-3


The filename argument specifies the filename to save 
the waveform data. The -c or --channel argument allows the 
user to choose between channel 1 or channel 2. The -p or --plot 
argument is a flag that, when provided, indicates that the waveform 
should be plotted. The cusor value is 50 milisec.


'''