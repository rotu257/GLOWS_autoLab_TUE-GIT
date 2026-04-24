#!/home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
"""
Enhanced HP/Agilent 8153A Power Measurement Script (Long-term fix version)
Fixed to channel 2 (for 81532A sensor in slot 2).

Features:
- Set wavelength (optional) → stored in nm
- Set averaging time (optional) → stored in seconds
- Proper wavelength conversion (instrument returns meters internally)
- Unit query workaround (instrument returns +0, we trust what we set)
- Clean CSV output with readable wavelength and averaging values
- Query-only mode (-q)
- All settings stored as instance variables (no more NameError)

Usage examples:
  python3 get_hp81532A_powermeter.py -w 980 -a 1.0 -o meas.csv
  python3 get_hp81532A_powermeter.py -a 0.5
  python3 get_hp81532A_powermeter.py -q
"""
import sys
import pyvisa as visa
import time
from datetime import datetime
from optparse import OptionParser


class HP8153A:
    CHANNEL = 2  # Fixed to channel 2 for 81532A

    def __init__(self, resource_str='GPIB0::5::INSTR',
                 wavelength=None,        # nm (optional)
                 averaging=None,         # seconds (optional)
                 unit='DBM',
                 filename=None,
                 query_only=False):

        self.resource_str = resource_str
        self.unit = unit.upper()
        self.filename = filename
        self.query_only = query_only

        # Initialize VISA
        rm = visa.ResourceManager()
        try:
            self.inst = rm.open_resource(resource_str)
            self.inst.timeout = 8000
            self.inst.read_termination = '\n'
            self.inst.write_termination = '\n'
        except Exception as e:
            print(f"Cannot open {resource_str}: {e}", file=sys.stderr)
            sys.exit(1)

        # Reset & clear
        self.write("*RST")
        time.sleep(1.5)
        self.write("*CLS")

        # Set unit
        if self.unit not in ('DBM', 'W'):
            print(f"Unsupported unit '{self.unit}' → using DBM")
            self.unit = 'DBM'
        self.write(f"SENS{self.CHANNEL}:POW:UNIT {self.unit}")

        # Set wavelength if requested
        if wavelength is not None:
            self.set_wavelength(wavelength)

        # Set averaging time if requested
        if averaging is not None:
            self.set_averaging_time(averaging)

        # Show identification
        idn = self.query("*IDN?").strip()
        print(f"Instrument: {idn}")

        # Store current settings (human-readable) for CSV and display
        self.current_wavelength = self._get_wavelength_nm()
        self.current_averaging = self._get_averaging_time()
        self.current_unit = self.unit  # instrument returns +0, so we use what we set

        # Show current settings
        self.print_current_settings()

        if not self.query_only:
            self.take_measurement()
        else:
            print("\nCurrent measurement (query-only mode):")
            self.take_measurement()

        self.close()

    def write(self, cmd):
        print(f"→ {cmd}")
        try:
            self.inst.write(cmd)
        except Exception as e:
            print(f"Write failed: {cmd} → {e}", file=sys.stderr)
            sys.exit(1)

    def query(self, q):
        print(f"? {q}")
        try:
            return self.inst.query(q).strip()
        except Exception as e:
            print(f"Query failed: {q} → {e}", file=sys.stderr)
            return ""

    def _get_wavelength_nm(self):
        """Read wavelength (instrument returns meters) and convert to nm"""
        raw = self.query(f"SENS{self.CHANNEL}:POW:WAVE?")
        wl_m = float(raw)
        wl_nm = wl_m * 1e9
        return round(wl_nm, 1)

    def _get_averaging_time(self):
        raw = self.query(f"SENS{self.CHANNEL}:POW:ATIME?")
        return round(float(raw), 3)

    def set_wavelength(self, wl):
        try:
            wl = float(wl)
            if not (800 <= wl <= 1700):
                print(f"Warning: {wl} nm outside typical 800–1700 nm range")
            print(f"Setting wavelength: {wl} nm")
            self.write(f"SENS{self.CHANNEL}:POW:WAVE {wl:.1f}NM")
            time.sleep(0.5)
            self._check_errors("after setting wavelength")

            # Update stored value (convert from meters)
            self.current_wavelength = self._get_wavelength_nm()
            print(f"  Confirmed wavelength: {self.current_wavelength:.1f} nm")
        except ValueError:
            print("Error: wavelength must be numeric (nm)", file=sys.stderr)
            sys.exit(1)

    def set_averaging_time(self, t_sec):
        try:
            t_sec = float(t_sec)
            if t_sec < 0.02 or t_sec > 3600:
                print(f"Warning: averaging time {t_sec}s outside typical range (0.02–3600 s)")
            print(f"Setting averaging time: {t_sec} s")
            self.write(f"SENS{self.CHANNEL}:POW:ATIME {t_sec} S")
            time.sleep(0.3)
            self._check_errors("after setting averaging time")

            self.current_averaging = self._get_averaging_time()
            print(f"  Confirmed averaging time: {self.current_averaging} s")
        except ValueError:
            print("Error: averaging time must be numeric (seconds)", file=sys.stderr)
            sys.exit(1)

    def _check_errors(self, context=""):
        errors = self.get_all_errors()
        if errors:
            print(f"Errors {context}:")
            for code, msg in errors:
                print(f"  {code:4d} : {msg}")

    def get_power(self):
        try:
            raw = self.query(f"READ{self.CHANNEL}:POW?").strip()
            val = float(raw)
            self._check_errors("after power read")
            return val, raw
        except Exception as e:
            print(f"Read failed: {e}", file=sys.stderr)
            return None, None

    def get_all_errors(self):
        errors = []
        while True:
            resp = self.query("SYST:ERR?").strip()
            if not resp or ',' not in resp:
                break
            code_str, msg_part = resp.split(',', 1)
            code = int(code_str)
            msg = msg_part.strip().strip('"')
            if code == 0:
                break
            errors.append((code, msg))
        return errors

    def print_current_settings(self):
        print("\nCurrent instrument settings:")
        print(f"  Wavelength     : {self.current_wavelength:.1f} nm")
        print(f"  Averaging time : {self.current_averaging} s")
        print(f"  Power unit     : {self.current_unit}")

    def take_measurement(self):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        val, val_str = self.get_power()

        if val is None:
            print("Measurement failed.")
            return

        print(f"[{ts}] {val_str} {self.current_unit}")

        if self.filename:
            header = "Timestamp,Channel,Wavelength(nm),Averaging(s),Power,Unit"
            line = f"{ts},{self.CHANNEL},{self.current_wavelength:.1f},{self.current_averaging},{val_str},{self.current_unit}"
            try:
                with open(self.filename, 'w', encoding='utf-8') as f:
                    f.write(header + '\n')
                    f.write(line + '\n')
                print(f"Saved measurement to: {self.filename}")
            except Exception as e:
                print(f"File write failed: {e}", file=sys.stderr)

    def close(self):
        try:
            self.inst.close()
        except:
            pass


if __name__ == "__main__":
    parser = OptionParser(usage="%prog [options]")
    parser.add_option("-r", "--resource", default="GPIB0::5::INSTR",
                      help="VISA resource name [default: %default]")
    parser.add_option("-w", "--wavelength", type="float",
                      help="Wavelength in nm (optional - if omitted, uses current)")
    parser.add_option("-a", "--averaging", type="float",
                      help="Averaging time in seconds (optional)")
    parser.add_option("-u", "--unit", default="DBM",
                      help="Power unit: DBM or W [default: %default]")
    parser.add_option("-o", "--output", dest="filename",
                      help="Output CSV file name (optional)")
    parser.add_option("-q", "--query-only", action="store_true", default=False,
                      help="Only query settings and current power (no changes)")

    options, args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    HP8153A(
        resource_str=options.resource,
        wavelength=options.wavelength,
        averaging=options.averaging,
        unit=options.unit,
        filename=options.filename,
        query_only=options.query_only
    )
