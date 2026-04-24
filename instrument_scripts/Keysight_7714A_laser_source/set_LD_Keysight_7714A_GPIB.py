#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
import pyvisa
import time
import argparse
import logging
from datetime import datetime


def setup_logging():
    """Configure logging to laser_status.log for status queries."""
    logging.basicConfig(
        filename='laser_status.log',
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def connect_instrument(address):
    """Connect to the instrument and return the resource object."""
    try:
        rm = pyvisa.ResourceManager()
        inst = rm.open_resource(address)
        inst.timeout = 20000  # 20 seconds timeout
        inst.write_termination = '\n'
        inst.read_termination = '\n'
        inst.write('*CLS')
        time.sleep(0.5)
        print("Connected to:", inst.query('*IDN?').strip())
        return inst
    except pyvisa.VisaIOError as e:
        print(f"Error connecting to instrument: {e}")
        return None


def clear_errors(instrument):
    """Clear all errors from the instrument's error queue."""
    try:
        errors = []
        while True:
            error = instrument.query('SYST:ERR?').strip()
            if '0,' in error:
                break
            errors.append(error)
        if errors:
            print("Cleared errors:", errors)
        else:
            print("Error queue was already empty or cleared.")
        return True
    except pyvisa.VisaIOError as e:
        print(f"Error clearing error queue: {e}")
        return False


def query_parameters(instrument, channel):
    """Query current wavelength, power, auto mode, laser state and valid ranges."""
    try:
        # Force power unit to dBm for consistent querying
        instrument.write(f':SOURce{channel}:POWer:UNIT DBM')
        time.sleep(0.3)

        wavelength = float(instrument.query(f':SOURce{channel}:WAVelength?')) * 1e9
        time.sleep(0.3)

        power_dbm = float(instrument.query(f':SOURce{channel}:POWer?'))
        time.sleep(0.3)

        auto_mode = instrument.query(f':SOURce{channel}:WAVelength:AUTO?').strip()
        time.sleep(0.3)

        laser_state = instrument.query(f':SOURce{channel}:POWer:STATe?').strip()
        time.sleep(0.3)

        # Wavelength range
        wl_min = float(instrument.query(f':SOURce{channel}:WAVelength? MIN')) * 1e9
        time.sleep(0.3)
        wl_max = float(instrument.query(f':SOURce{channel}:WAVelength? MAX')) * 1e9
        time.sleep(0.3)

        # Power range (in dBm, after unit set)
        p_min = float(instrument.query(f':SOURce{channel}:POWer? MIN'))
        time.sleep(0.3)
        p_max = float(instrument.query(f':SOURce{channel}:POWer? MAX'))
        time.sleep(0.3)

        status = {
            'Channel': channel,
            'Wavelength (nm)': wavelength,
            'Power (dBm)': power_dbm,
            'Auto Mode': auto_mode,
            'Laser State': 'ON' if laser_state == '1' else 'OFF',
            'Wavelength Range (nm)': [wl_min, wl_max],
            'Power Range (dBm)': [p_min, p_max]
        }

        print(f"Channel {channel} settings:")
        print(f"  Wavelength   = {wavelength:8.3f} nm")
        print(f"  Power        = {power_dbm:6.2f} dBm")
        print(f"  Auto Mode    = {auto_mode}")
        print(f"  Laser State  = {status['Laser State']}")
        print(f"  Valid wavelength = [{wl_min:8.3f}, {wl_max:8.3f}] nm")
        print(f"  Valid power      = [{p_min:6.2f}, {p_max:6.2f}] dBm")

        return status
    except pyvisa.VisaIOError as e:
        print(f"Error querying parameters: {e}")
        return None


def log_status(instrument, channel):
    """Log high-level status to laser_status.log."""
    status = query_parameters(instrument, channel)
    if status:
        log_message = (
            f"Channel {channel}: "
            f"Wavelength={status['Wavelength (nm)']:.3f} nm, "
            f"Power={status['Power (dBm)']:.2f} dBm, "
            f"Auto Mode={status['Auto Mode']}, "
            f"Laser State={status['Laser State']}, "
            f"Valid wavelength=[{status['Wavelength Range (nm)'][0]:.1f}, "
            f"{status['Wavelength Range (nm)'][1]:.1f}] nm, "
            f"Valid power=[{status['Power Range (dBm)'][0]:.2f}, "
            f"{status['Power Range (dBm)'][1]:.2f}] dBm"
        )
        logging.info(log_message)
        print(f"Status logged: {log_message}")


def set_wavelength(instrument, channel, wavelength_m):
    """Set wavelength in meters."""
    try:
        wavelength_nm = wavelength_m * 1e9
        wl_min = float(instrument.query(f':SOURce{channel}:WAVelength? MIN')) * 1e9
        wl_max = float(instrument.query(f':SOURce{channel}:WAVelength? MAX')) * 1e9
        time.sleep(0.5)

        if not (wl_min <= wavelength_nm <= wl_max):
            print(f"Wavelength {wavelength_nm:.3f} nm out of range "
                  f"[{wl_min:.1f}, {wl_max:.1f}] nm")
            return False

        instrument.write(f':SOURce{channel}:WAVelength:AUTO ON')
        time.sleep(0.5)
        instrument.write(f':SOURce{channel}:WAVelength {wavelength_nm:.6f}NM')
        time.sleep(1.0)

        error = instrument.query('SYST:ERR?').strip()
        if '0,' in error:
            print(f"Set channel {channel} wavelength → {wavelength_nm:.3f} nm")
            return True
        else:
            print(f"Error setting wavelength: {error}")
            return False

    except pyvisa.VisaIOError as e:
        print(f"Error setting wavelength: {e}")
        return False


def set_power(instrument, channel, power_dbm):
    """Set output power in dBm."""
    try:
        # Force power unit to dBm
        instrument.write(f':SOURce{channel}:POWer:UNIT DBM')
        time.sleep(0.3)

        # Query range in dBm
        p_min = float(instrument.query(f':SOURce{channel}:POWer? MIN'))
        p_max = float(instrument.query(f':SOURce{channel}:POWer? MAX'))
        time.sleep(0.5)

        if not (p_min <= power_dbm <= p_max):
            print(f"Power {power_dbm:.2f} dBm out of range "
                  f"[{p_min:.2f}, {p_max:.2f}] dBm")
            return False

        instrument.write(f':SOURce{channel}:POWer {power_dbm:.3f}DBM')
        time.sleep(0.8)

        error = instrument.query('SYST:ERR?').strip()
        if '0,' in error:
            print(f"Set channel {channel} power → {power_dbm:.2f} dBm")
            time.sleep(1.0)
            actual = float(instrument.query(f':SOURce{channel}:POWer?'))
            print(f"  → actual/readback: {actual:.2f} dBm")
            return True
        else:
            print(f"Error setting power: {error}")
            return False

    except pyvisa.VisaIOError as e:
        print(f"Error setting power: {e}")
        return False


def set_laser_state(instrument, channel, state):
    """Set the laser state ON (1) / OFF (0)."""
    try:
        state_cmd = 'ON' if state == 1 else 'OFF'
        instrument.write(f":SOURce{channel}:POWer:STATe {state_cmd}")
        time.sleep(0.8)

        error = instrument.query('SYST:ERR?').strip()
        if '0,' in error:
            print(f"Laser channel {channel} → {state_cmd}")
            return True
        else:
            print(f"Error setting laser state: {error}")
            return False

    except pyvisa.VisaIOError as e:
        print(f"Error setting laser state: {e}")
        return False


def execute_scpi(instrument, command):
    """Execute an arbitrary SCPI command or query."""
    try:
        if command.endswith('?'):
            result = instrument.query(command).strip()
            time.sleep(0.3)
            error = instrument.query('SYST:ERR?').strip()
            if '0,' in error:
                print(f"Query '{command}' → {result}")
                return result
            else:
                print(f"Error on query '{command}': {error}")
                return None
        else:
            instrument.write(command)
            time.sleep(0.5)
            error = instrument.query('SYST:ERR?').strip()
            if '0,' in error:
                print(f"Command '{command}' executed OK")
                return True
            else:
                print(f"Error on command '{command}': {error}")
                return False
    except pyvisa.VisaIOError as e:
        print(f"Visa error executing '{command}': {e}")
        return False


def main():
    examples = """
Examples:
  # Show help
  python %(prog)s -h

  # Query current status of default channel (1) and log it
  python %(prog)s --status

  # Set channel 3 to 1550.12 nm, 10.5 dBm and turn output ON
  python %(prog)s -S 3 -w 1.55012e-6 -p 10.5 -o 1 --status

  # Only change power on channel 2 (laser must already be on)
  python %(prog)s -S 2 -p 13.0

  # Turn laser OFF on channel 4
  python %(prog)s -S 4 -o 0

  # Read current power setting (query)
  python %(prog)s -q ":SOURce1:POWer?"

  # Set wavelength and power, then show status
  python %(prog)s -w 1.560e-6 -p 8.0 --status
"""

    parser = argparse.ArgumentParser(
        description="Control Keysight N7714A Tunable Laser (GPIB)",
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-S', '--source', type=int, choices=[1,2,3,4],
                        help="Select source channel (1-4)")
    parser.add_argument('-w', '--wavelength', type=float,
                        help="Set wavelength in meters (e.g. 1.550e-6)")
    parser.add_argument('-p', '--power', type=float,
                        help="Set optical power in dBm (e.g. 10.0)")
    parser.add_argument('-o', '--output', type=int, choices=[0, 1],
                        help="Laser output: 1 = ON, 0 = OFF")
    parser.add_argument('-q', '--scpi', type=str,
                        help="Execute arbitrary SCPI command/query")
    parser.add_argument('--status', action='store_true',
                        help="Query and log current status")

    args = parser.parse_args()

    if not any([args.source, args.wavelength, args.power is not None,
                args.output is not None, args.scpi, args.status]):
        parser.error("At least one action must be specified (-S, -w, -p, -o, -q, --status)")

    channel = args.source if args.source else 1

    if args.status:
        setup_logging()

    address = 'GPIB0::21::INSTR'
    inst = connect_instrument(address)
    if not inst:
        return

    try:
        if not clear_errors(inst):
            print("Failed to clear errors → exiting.")
            return

        if args.scpi:
            execute_scpi(inst, args.scpi)

        if args.wavelength:
            set_wavelength(inst, channel, args.wavelength)

        if args.power is not None:
            set_power(inst, channel, args.power)

        if args.output is not None:
            set_laser_state(inst, channel, args.output)

        if args.status:
            log_status(inst, channel)

    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        inst.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()
