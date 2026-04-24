#!/home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

#!/home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

import numpy as np
import matplotlib.pyplot as plt

# ────────────────────────────────────────────────
# Configuration - file pairs for both channels
# ────────────────────────────────────────────────
channels = [
    {
        'name': 'Channel 3',
        'log_file': 'mywave_keysight_chan3.log',
        'txt_file': 'mywave_keysight_chan3.txt',
        'color': 'dodgerblue',
        'label': 'CH3'
    },
    {
        'name': 'Channel 4',
        'log_file': 'mywave_keysight_chan4.log',
        'txt_file': 'mywave_keysight_chan4.txt',
        'color': 'tomato',
        'label': 'CH4'
    }
]

# ────────────────────────────────────────────────
# Function to load one waveform
# ────────────────────────────────────────────────
def load_keysight_waveform(log_path, txt_path):
    # Read header from .log file
    with open(log_path, 'r') as f:
        header_str = f.read().strip()
        header = [float(h) if '.' in h or 'E' in h or 'e' in h else int(h) 
                  for h in header_str.split(',')]

    # Parse important parameters
    N_expected = int(header[2])
    xincr     = header[4]
    xorigin   = header[5]
    xref      = int(header[6])
    yincr     = header[7]
    yorigin   = header[8]
    yref      = int(header[9])

    # Read data from .txt file
    with open(txt_path, 'r') as f:
        content = f.read().replace('\n', ',')
        data_str = content.split(',')

    # Extract numeric values only
    y_raw = []
    for s in data_str:
        s = s.strip()
        if s:
            try:
                y_raw.append(float(s))
            except ValueError:
                pass

    y = np.array(y_raw)
    N_actual = len(y)

    if N_actual != N_expected:
        print(f"Warning: {log_path} → Found {N_actual} points, expected {N_expected}")

    # Use the smaller length to avoid index errors
    N = min(N_expected, N_actual)
    y = y[:N]

    # Time axis
    t = xorigin + (np.arange(N) - xref) * xincr

    return t, y, N


# ────────────────────────────────────────────────
# Load both channels
# ────────────────────────────────────────────────
waveforms = []
for ch in channels:
    try:
        t, y, N = load_keysight_waveform(ch['log_file'], ch['txt_file'])
        waveforms.append((t, y, ch))
        print(f"Loaded {ch['name']} – {N} points")
    except FileNotFoundError as e:
        print(f"Skipping {ch['name']}: {e}")
    except Exception as e:
        print(f"Error loading {ch['name']}: {e}")


# ────────────────────────────────────────────────
# Plot
# ────────────────────────────────────────────────
if not waveforms:
    print("No waveforms could be loaded.")
else:
    plt.figure(figsize=(14, 7))

    for t, y, ch in waveforms:
        plt.plot(t * 1e3, y,               # time in ms for readability
                 color=ch['color'],
                 linewidth=0.8,
                 label=ch['label'])

    plt.xlabel('Time (ms)')
    plt.ylabel('Voltage (V)')
    plt.title('Keysight DSOX2024A – CH3 and CH4 Waveforms')
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.legend()
    plt.tight_layout()

    plt.show()

    # Optional: save
    # plt.savefig('ch3_ch4_waveforms.png', dpi=400, bbox_inches='tight')

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