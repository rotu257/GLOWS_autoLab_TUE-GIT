#!/home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

import numpy as np
import matplotlib.pyplot as plt

# File paths (adjust if necessary)
log_file = 'mywave_keysight_keysight_chan3.log'
txt_file = 'mywave_keysight_keysight_chan3.txt'


# Read header from .log file
with open(log_file, 'r') as f:
    header_str = f.read().strip()
    header = [float(h) if '.' in h or 'E' in h or 'e' in h else int(h) for h in header_str.split(',')]

# Parse header (based on standard Keysight/Agilent waveform export format)
# Indices: [0: ?, 1: ?, 2: N_points, 3: ?, 4: x_increment, 5: x_origin, 6: x_reference, 7: y_increment, 8: y_origin, 9: y_reference]
N_expected = int(header[2])  # Expected number of points
xincr = header[4]
xorigin = header[5]
xref = int(header[6])
yincr = header[7]
yorigin = header[8]
yref = int(header[9])

# Read data from .txt file (comma-separated, may have header comment like #...)
with open(txt_file, 'r') as f:
    content = f.read().replace('\n', ',')  # Handle multi-line if needed
    data_str = content.split(',')

# Extract numeric values (skip non-numeric like comments)
y_raw = []
for s in data_str:
    s = s.strip()
    if s:
        try:
            y_raw.append(float(s))
        except ValueError:
            pass  # Skip non-numeric

# Convert to numpy array
y = np.array(y_raw)

# Check if the number of points matches the expected number
N_actual = len(y)
if N_actual != N_expected:
    print(f"Warning: Found {N_actual} points, expected {N_expected}. Adjusting time array to match.")

# Use the actual number of points for the time array
N = min(N_expected, N_actual)  # Use the smaller of the two to avoid mismatch
y = y[:N]  # Truncate y if necessary (though it should already be the correct length)

# Generate time axis based on actual number of points
t = xorigin + (np.arange(N) - xref) * xincr

# Plot
plt.figure(figsize=(12, 6))
plt.plot(t, y, linewidth=0.5)
plt.xlabel('Time (s)')
plt.ylabel('Voltage (V)')
plt.title('Keysight/Agilent DSOX2024A Oscilloscope - Channel ? Waveform')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# Optional: Save plot
# plt.savefig('waveform_plot.png', dpi=300)

'''
Each value corresponds to a specific parameter of the waveform capture, as is typical for Keysight oscilloscope 
waveform exports in ASCII format. Based on standard Keysight/Agilent waveform file formats (e.g., for DSO-X series 
oscilloscopes), here’s a breakdown of what each field likely represents:

+4 (Waveform Type or Channel):

Likely indicates the waveform type or channel number. Here, +4 suggests the data is from Channel 4 of the oscilloscope.


+3 (Waveform Format or Source):

May indicate the waveform format (e.g., ASCII, binary) or the source of the data. A value of +3 is less common but could denote a specific mode or configuration (e.g., normal acquisition mode).


+7680 (Number of Points, N):

Specifies the total number of data points in the waveform. Here, the oscilloscope captured 7680 samples for this waveform.


+1 (Count or Acquisition Type):

Likely represents the acquisition count or type (e.g., single acquisition). A value of +1 typically means a single capture.


+2.60416562E-007 (X Increment, Δt):

The time increment between consecutive data points, in seconds. Here, 2.60416562E-007 seconds (or approximately 260.4 ns) is the time step between samples.
This defines the sampling interval, so the sampling rate is 1 / Δt ≈ 3.84 MSa/s (megasamples per second).


-1.00000000E-003 (X Origin):

The time value of the first data point, in seconds. Here, -1.00000000E-003 seconds (or -1 ms) indicates the starting point of the time axis relative to the trigger point.
A negative value suggests the waveform includes pre-trigger data (samples before the trigger event).


+0 (X Reference):

The reference point for the time axis, often the index of the trigger point in the data array. A value of 0 indicates the trigger point is at the start of the waveform data.


+7.85175900E-004 (Y Increment, ΔV):

The voltage increment per unit of the raw data, in volts. Here, 7.85175900E-004 volts (or approximately 785.2 µV) is the voltage resolution per ADC (analog-to-digital converter) count.
This is used to convert raw ADC values to physical voltage values if the .txt file contains raw data.


+0.0E+000 (Y Origin):

The voltage corresponding to a raw data value of zero, in volts. Here, 0.0 volts indicates the zero point of the voltage scale (e.g., the ground reference).


+32768 (Y Reference):

The reference ADC value corresponding to the Y origin (0 volts). A value of 32768 is typical for a 16-bit signed ADC centered around zero (e.g., for a 16-bit ADC, 32768 is the midpoint of the range -32768 to +32767).
This is used to scale raw ADC values to voltages: V = Y_origin + (raw_value - Y_reference) * Y_increment.

'''