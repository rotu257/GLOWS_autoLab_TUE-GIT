#!/home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
"""
MPM-210H System Check Script via GPIB Communication

This script performs system-related queries on the MPM-210H instrument using GPIB at address 16.
The GPIB address is hard-coded as 16. If needed, modify the GPIB_ADDRESS variable.

System Check Commands:
  - *CLS       : Clear status and error queue.
  - *RST       : Reset the instrument to default settings.
  - *IDN?      : Check instrument identification.
  - ERR?       : Check error information.
  - IDIS?      : Check recognition of measurement modules.
  - MMVER? 0   : Identification query of module type for module slot 0.
  - ADDR?      : Read out the GPIB address.
  - GW?        : Read out the Gateway address.
  - SUBNET?    : Read out the Subnet mask.
  - IP?        : Read out the IP address.

Usage:
  To perform the system check, run the script with the --system-check flag:
    $ ./check_mpm210h_system.py --system-check

  If no operation is specified, the script will exit with a usage message.
"""

import sys
import pyvisa
import argparse

# Hard-coded GPIB address
GPIB_ADDRESS = 16

class MPM210H:
    def __init__(self, resource):
        self.resource = resource
        try:
            rm = pyvisa.ResourceManager()  # Use default backend (NI-VISA or compatible)
            print(f"Available resources: {rm.list_resources()}")
            self.device = rm.open_resource(self.resource)
            self.device.timeout = 10000
            self.device.read_termination = "\n"
            self.device.write_termination = "\n"
            print(f"Successfully connected to {self.resource}")
        except Exception as e:
            print(f"\nError: Could not open resource {self.resource}")
            print(f"Details: {e}\n")
            sys.exit(1)

    def send_command(self, command):
        print(f"\nSending command: {command}")
        try:
            self.device.write(command)
            print("Command executed.\n")
        except Exception as e:
            print(f"Error sending command: {e}")
            sys.exit(1)

    def query(self, command):
        print(f"\nQuerying with command: {command}")
        try:
            self.device.write(command)
            response = self.device.read()
            print(f"Response: {response}\n")
            return response
        except Exception as e:
            print(f"Error during query: {e}")
            sys.exit(1)

def system_check(mpm):
    # Clear status and error queue
    print("\nClearing status and error queue:")
    try:
        mpm.send_command("*CLS")
        print("Checking error state after *CLS:")
        mpm.query("ERR?")
    except Exception as e:
        print(f"Error during *CLS or ERR? query: {e}")

    # Reset the instrument
    print("\nResetting instrument to default settings:")
    try:
        mpm.send_command("*RST")
        print("Checking error state after *RST:")
        mpm.query("ERR?")
    except Exception as e:
        print(f"Error during *RST or ERR? query: {e}")

    # System-related queries
    commands = {
        "ID Information (*IDN?)": "*IDN?",
        "Error Information (ERR?)": "ERR?",
        "Module Recognition (IDIS?)": "IDIS?",
        "Module Identification (MMVER? 0)": "MMVER? 0",
        "GPIB Address (ADDR?)": "ADDR?",
        "Gateway Address (GW?)": "GW?",
        "Subnet Mask (SUBNET?)": "SUBNET?",
        "IP Address (IP?)": "IP?"
    }
    print("\nPerforming system check queries:")
    for description, cmd in commands.items():
        print(f"\n{description}:")
        try:
            mpm.query(cmd)
        except Exception as e:
            print(f"Command {cmd} failed: {e}")
    print("System check completed.\n")

def main():
    parser = argparse.ArgumentParser(
        description="MPM-210H System Check Script via GPIB Connection."
    )
    parser.add_argument("--system-check", action="store_true",
                        help="Perform system-related queries on the instrument")
    args = parser.parse_args()

    resource = f"GPIB0::{GPIB_ADDRESS}::INSTR"
    print(f"\nConnecting to resource: {resource}")
    mpm = MPM210H(resource)

    if args.system_check:
        system_check(mpm)
    else:
        print("\nNo operation specified. Use --system-check to perform system queries.\n")
        sys.exit(0)

if __name__ == "__main__":
    main()