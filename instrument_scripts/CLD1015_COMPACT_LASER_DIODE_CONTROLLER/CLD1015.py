#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
import sys
import pyvisa as visa
import argparse

class CLD1015:
    def __init__(self, resource):
        self.resource = resource
        try:
            rm = visa.ResourceManager('@py')
            self.device = rm.open_resource(self.resource)
        except Exception as e:
            print(f"\nError: Could not open resource {self.resource}")
            print(f"Details: {e}\n")
            sys.exit(1)

    def send_command(self, command):
        """Send a SCPI command to the instrument."""
        print(f"\nSending command: {command}")
        try:
            self.device.write(command)
            print("Command executed.\n")
        except Exception as e:
            print(f"Error sending command: {e}")
            sys.exit(1)

    def query(self, command):
        """Send a SCPI query and print the response."""
        print(f"\nQuerying with command: {command}")
        try:
            self.device.write(command)
            response = self.device.read()
            print(f"Response: {response}\n")
            return response
        except Exception as e:
            print(f"Error during query: {e}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Control the CLD1015 instrument via SCPI commands. "
                    "Refer to the CLD1015 Programmer's Reference Manual :contentReference[oaicite:2]{index=2}&#8203;:contentReference[oaicite:3]{index=3} for details."
    )
    parser.add_argument("address", type=int,
                        help="Device address identifier (e.g., 1, 2)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-q", "--query", type=str,
                       help="SCPI query to send (e.g., '*IDN?')")
    group.add_argument("-c", "--command", type=str,
                       help="Generic SCPI command to send (e.g., '*CLS')")
    group.add_argument("--state", type=str, choices=["ON", "OFF", "1", "0"],
                       help="Set laser output state. 'ON' or '1' enables and 'OFF' or '0' disables the laser (SCPI: OUTPut1:STATe).")
    group.add_argument("--current", type=float,
                       help="Set the laser current setpoint in amps (SCPI: SOURce1:CURRent:LEVel:IMMediate).")
    
    args = parser.parse_args()

    # Map the provided address identifier to a VISA resource string.
    # Update these resource strings to match your actual CLD1015 devices.
    if args.address == 1:
        resource = 'USB0::4883::32847::M01053290::0::INSTR'
    elif args.address == 2:
        resource = 'USB0::1234::5678::CLD1015-002::0::INSTR'
    else:
        print("\nError: Unknown device identifier provided.\n")
        sys.exit(1)

    cld = CLD1015(resource)

    # Handle the different command modes
    if args.query:
        cld.query(args.query)
    elif args.command:
        cld.send_command(args.command)
    elif args.state is not None:
        # Normalize state input: convert "1" to "ON" and "0" to "OFF"
        state = "ON" if args.state in ["ON", "1"] else "OFF"
        # According to the manual, the command to enable/disable the LD output is:
        #   OUTPut[1][:STATe] {ON|1|OFF|0}
        command = f"OUTPut1:STATe {state}"
        cld.send_command(command)
    elif args.current is not None:
        # Set the laser current setpoint using the SCPI command:
        #   SOURce[1]:CURRent:LEVel:IMMediate <amps>
        command = f"SOURce1:CURRent:LEVel:IMMediate {args.current}"
        cld.send_command(command)

if __name__ == "__main__":
    main()


"""
CLD1015 Control Script

This script uses PyVISA to control the Thorlabs CLD1015 instrument via SCPI commands.
It supports the following operations:
  1. Sending a generic SCPI command.
  2. Issuing a SCPI query.
  3. Setting the laser output state (ON/OFF).
  4. Setting the laser current setpoint.

Usage Examples:
--------------
1. Query the device identification string:
   $ ./setinstrument_CLD1015.py -q "*IDN?" 1

2. Send a generic command (e.g., clear status registers):
   $ ./setinstrument_CLD1015.py -c "*CLS" 1

3. Set the laser output state (turn laser ON):
   $ ./setinstrument_CLD1015.py --state ON 1
   (You can also use "1" instead of "ON", or "OFF"/"0" to turn off.)

4. Set the laser current setpoint (e.g., 1.23 amps):
   $ ./setinstrument_CLD1015.py --current 1.23 1

Device Address Mapping:
-----------------------
Address identifier 1 maps to:
   USB0::1234::5678::CLD1015-001::0::INSTR
Address identifier 2 maps to:
   USB0::1234::5678::CLD1015-002::0::INSTR

For additional details, please refer to the CLD1015 Programmer's Reference Manual.
"""