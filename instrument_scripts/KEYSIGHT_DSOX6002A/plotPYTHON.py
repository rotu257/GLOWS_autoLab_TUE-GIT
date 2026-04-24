import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# ────────────────────────────────────────────────
#  Load both CSV files
#  Assumes format: first column = time (s), second = voltage (V)
#  Skip header rows if your files have them (adjust skiprows if needed)
# ────────────────────────────────────────────────

df1 = pd.read_csv('DSOX6002A_OSCwaveform_oldscript_6000X_chan2_scaled.csv', skiprows=1, header=None,
                  names=['time', 'voltage'])
df2 = pd.read_csv('DSOX6002A_OSCwaveform_oldscript_6000X_chan2_scaled.csv', skiprows=1, header=None,
                  names=['time', 'voltage'])

t1 = df1['time'].values
v1 = df1['voltage'].values

t2 = df2['time'].values
v2 = df2['voltage'].values

# ────────────────────────────────────────────────
#  Create the plot
# ────────────────────────────────────────────────

plt.figure(figsize=(10, 6), dpi=100)

plt.plot(t1, v1, 'b-', linewidth=1.5, label='scope_1_1')
plt.plot(t2, v2, 'r--', linewidth=1.5, label='scope1_2')

plt.xlabel('Time (s)')
plt.ylabel('Voltage (V)')
plt.title('Oscilloscope Capture Comparison\nscope_1_1 vs scope1_2')
plt.grid(True, alpha=0.7, linestyle='--')
plt.legend(loc='best', fontsize=10)
plt.tight_layout()

# Optional: zoom into the interesting region (uncomment & adjust)
# plt.xlim(-0.06, 0.06)
# plt.ylim(-0.002, 0.015)

plt.show()
