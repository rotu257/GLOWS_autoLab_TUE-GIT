import numpy as np
import matplotlib.pyplot as plt

# Load the data
data = np.loadtxt('/home/user_rotu/GLOWS_autoLab_python3_venv/instrument_scripts/hp70952b_OSA/HP70952B_OSA_probescanb_test')

wavelength = data[:, 0]
amplitude = data[:, 1]

# Create the plot
plt.figure()
plt.plot(wavelength, amplitude)
plt.xlabel('Wavelength (nm)')
plt.ylabel('Amplitude')
plt.title('Spectral Scan')
plt.grid(True)
plt.tight_layout()
plt.show()
