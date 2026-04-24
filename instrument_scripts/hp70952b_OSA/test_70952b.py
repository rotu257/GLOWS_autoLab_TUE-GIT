#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

import pyvisa
import numpy as np

# ——— USER PARAMETERS ———
GPIB_ADDR = 23       # HP-IB address of the 70952B
TIMEOUT_MS = 5000    # Visa timeout
START_WL = '1400NM'  # start wavelength
STOP_WL  = '1600NM'  # stop wavelength
POINTS    = 800     # number of points in scan
FILENAME  = 'scan_data2.txt'
# ————————————————————

# 1) Open resource manager and instrument
rm   = pyvisa.ResourceManager()
inst = rm.open_resource(f'GPIB0::{GPIB_ADDR}::INSTR')

# 2) Configure timeouts & terminations
inst.timeout          = TIMEOUT_MS
inst.write_termination = '\n'
inst.read_termination  = '\n'

# 3) Put instrument into remote HP-IB control
inst.write(f'REMOTE {GPIB_ADDR}')                   # Place all devices in remote status :contentReference[oaicite:0]{index=0}&#8203;:contentReference[oaicite:1]{index=1}

# 4) Clear status and error queue
inst.clear()                                        # HP-IB Device Clear

# 5) Preset the analyzer
inst.write('IP')                                    # Instrument preset :contentReference[oaicite:2]{index=2}&#8203;:contentReference[oaicite:3]{index=3}

# 6) Set up a single sweep
inst.write(f'STARTWL {START_WL};STOPWL {STOP_WL};')  # Span parameters
inst.write(f'NPOINTS {POINTS};')                    # Points per sweep
inst.write('SNGLS;TS')                              # Single sweep, trigger sweep :contentReference[oaicite:4]{index=4}&#8203;:contentReference[oaicite:5]{index=5}

# 7) Read back the trace in ASCII (comma‐separated floats)
raw = inst.query('TRA?')                            # Query all trace (A) data :contentReference[oaicite:6]{index=6}&#8203;:contentReference[oaicite:7]{index=7}
data = np.fromstring(raw, sep=',')                  # Parse into NumPy array

# 8) Save every point to a .txt file
np.savetxt(FILENAME, data, fmt='%.6f', header='Wavelength (nm) vs. Amplitude')

# 9) Return the OSA to local (front‐panel) control
inst.write('LOCAL')                                 # Return to local control :contentReference[oaicite:8]{index=8}&#8203;:contentReference[oaicite:9]{index=9}

# 10) Clean up
inst.close()
rm.close()

print(f"Saved {len(data)} points to {FILENAME}")
