#!/home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

import pyvisa
import time
import sys
import argparse
import json
import uuid

class OVAController:
    def __init__(self, visa_address, timeout=5000):
        """Initialize the OVA Controller with VISA address."""
        self.visa_address = visa_address
        self.timeout = timeout  # Timeout in milliseconds
        self.instrument = None

    def connect(self):
        """Establish USB connection to the OVA using VISA."""
        try:
            rm = pyvisa.ResourceManager()
            self.instrument = rm.open_resource(self.visa_address)
            self.instrument.timeout = self.timeout
            self.instrument.write_termination = '\n'
            self.instrument.read_termination = '\n'
            print(f"Connected to OVA at {self.visa_address}")
        except Exception as e:
            print(f"Connection failed: {e}")
            sys.exit(1)

    def disconnect(self):
        """Close the USB connection."""
        if self.instrument:
            self.instrument.close()
            print("Disconnected from OVA")
            self.instrument = None

    def send_command(self, command):
        """Send an SCPI command to the OVA."""
        try:
            self.instrument.write(command)
            time.sleep(0.1)  # Small delay to ensure command execution
        except Exception as e:
            print(f"Error sending command '{command}': {e}")

    def query(self, command):
        """Send an SCPI query and return the response."""
        try:
            response = self.instrument.query(command)
            return response.strip()
        except Exception as e:
            print(f"Error querying '{command}': {e}")
            return None

    def reset_device(self):
        """Reset the OVA to its default state."""
        self.send_command("*RST")
        self.send_command("*CLS")  # Clear status
        print("Device reset and status cleared")
        time.sleep(1)  # Allow reset to complete

    def get_device_info(self):
        """Query and return device identification."""
        return self.query("*IDN?")

    def get_system_version(self):
        """Query and return system version."""
        return self.query(":SYSTem:VERSion?")

    def set_wavelength(self, wavelength):
        """Set the wavelength in nm (1200 to 1700 for single-mode long)."""
        if 1200 <= wavelength <= 1700:  # Adjust range based on OVA model
            self.send_command(f"Input:WAVelength {wavelength}")
            print(f"Wavelength set to {wavelength} nm")
        else:
            print(f"Wavelength {wavelength} nm is out of range (1200-1700 nm)")

    def get_wavelength(self):
        """Query the current wavelength."""
        return self.query("Input:WAVelength?")

    def set_attenuation(self, attenuation):
        """Set the attenuation in dB (0 to 100 for single-mode long)."""
        if 0 <= attenuation <= 100:  # Adjust range based on OVA model
            self.send_command(f"Input:ATTenuation {attenuation}")
            print(f"Attenuation set to {attenuation} dB")
        else:
            print(f"Attenuation {attenuation} dB is out of range (0-100 dB)")

    def get_attenuation(self):
        """Query the current attenuation."""
        return self.query("Input:ATTenuation?")

    def set_offset(self, offset):
        """Set the attenuation offset in dB."""
        self.send_command(f"Input:OFFSet {offset}")
        print(f"Attenuation offset set to {offset} dB")

    def set_absolute_power_mode(self, enable):
        """Enable or disable absolute power mode (1 = enabled, 0 = disabled)."""
        self.send_command(f"OUTPUT:APMode {1 if enable else 0}")
        print(f"Absolute power mode {'enabled' if enable else 'disabled'}")

    def set_power_setpoint(self, power):
        """Set the power setpoint in dBm (requires power monitoring option)."""
        self.send_command(f"OUTPUT:POWER {power}")
        print(f"Power setpoint set to {power} dBm")

    def get_power_setpoint(self):
        """Query the current power setpoint in dBm."""
        return self.query("OUTPUT:POWER?")

    def set_power_leveling(self, enable):
        """Enable or disable power leveling (1 = enabled, 0 = disabled)."""
        self.send_command(f"OUTPUT:TRACKing {1 if enable else 0}")
        print(f"Power leveling {'enabled' if enable else 'disabled'}")

    def set_drift_tolerance(self, tolerance):
        """Set the drift tolerance in dB for power leveling."""
        if tolerance > 0:
            self.send_command(f"OUTPUT:DRIFT {tolerance}")
            print(f"Drift tolerance set to {tolerance} dB")
        else:
            print("Drift tolerance must be greater than 0")

    def measure_dark_current(self):
        """Measure and store the dark current on the PD."""
        response = self.query("OUTPUT:DARK")
        print("Dark current measurement:", "Successful" if response == "1" else "Failed")
        return response

    def set_beam_block(self, enable):
        """Enable or disable the beam block (1 = enabled, 0 = disabled)."""
        self.send_command(f"OUTPUT:STATE {1 if enable else 0}")
        print(f"Beam block {'enabled' if enable else 'disabled'}")

    def set_interaction_mode(self, local):
        """Set interaction mode (1 = local, 0 = remote)."""
        self.send_command(f"LCL {1 if local else 0}")
        print(f"Interaction mode set to {'local' if local else 'remote'}")

    def get_interaction_mode(self):
        """Query the current interaction mode."""
        return self.query("LCL?")

    def set_lan_address(self, address):
        """Set the LAN IP address or enable DHCP."""
        self.send_command(f":SYSTem:COMMunicate:LAN:ADDRess {address}")
        print(f"LAN address set to {address}")

    def get_lan_address(self):
        """Query the current LAN IP address."""
        return self.query(":SYSTem:COMMunicate:LAN:ADDRess?")

    def set_lan_gateway(self, gateway):
        """Set the LAN gateway address."""
        self.send_command(f":SYSTem:COMMunicate:LAN:GATEway {gateway}")
        print(f"LAN gateway set to {gateway}")

    def get_lan_gateway(self):
        """Query the current LAN gateway address."""
        return self.query(":SYSTem:COMMunicate:LAN:GATEway?")

    def set_lan_mask(self, netmask):
        """Set the LAN subnet mask."""
        self.send_command(f":SYSTem:COMMunicate:LAN:MASK {netmask}")
        print(f"LAN subnet mask set to {netmask}")

    def get_lan_mask(self):
        """Query the current LAN subnet mask."""
        return self.query(":SYSTem:COMMunicate:LAN:MASK?")

    def set_lan_hostname(self, hostname):
        """Set the LAN hostname."""
        self.send_command(f":SYSTem:COMMunicate:LAN:HOSTname {hostname}")
        print(f"LAN hostname set to {hostname}")

    def get_lan_hostname(self):
        """Query the current LAN hostname."""
        return self.query(":SYSTem:COMMunicate:LAN:HOSTname?")

    def go_to_min_insertion_loss(self):
        """Set the attenuator to the minimum insertion loss point."""
        self.send_command("Input:ILMin")
        print("Set to minimum insertion loss point")

    def save_config(self, config_file):
        """Query the current configuration and save it to a file."""
        try:
            config = {
                "device_info": self.get_device_info(),
                "system_version": self.get_system_version(),
                "wavelength": self.get_wavelength(),
                "attenuation": self.get_attenuation(),
                "power_setpoint": self.get_power_setpoint(),
                "absolute_power_mode": self.query("OUTPUT:APMode?"),
                "power_leveling": self.query("OUTPUT:TRACKing?"),
                "drift_tolerance": self.query("OUTPUT:DRIFT?"),
                "beam_block": self.query("OUTPUT:STATE?"),
                "interaction_mode": self.get_interaction_mode(),
                "lan_address": self.get_lan_address(),
                "lan_gateway": self.get_lan_gateway(),
                "lan_mask": self.get_lan_mask(),
                "lan_hostname": self.get_lan_hostname()
            }
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=4)
            print(f"Configuration saved to {config_file}")
        except Exception as e:
            print(f"Error saving configuration to {config_file}: {e}")

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Control script for OVA Optical Attenuator over USB")
    parser.add_argument("--visa", default="USB0::9256::53254::2402256::0::INSTR", 
                        help="VISA address of the OVA (default: USB0::9256::53254::2402256::0::INSTR)")
    parser.add_argument("--action", required=True, 
                        choices=["reset", "info", "get_version", "set_wavelength", "get_wavelength", 
                                 "set_attenuation", "get_attenuation", "set_offset", 
                                 "set_power_mode", "set_power", "get_power", 
                                 "set_power_leveling", "set_drift_tolerance", 
                                 "measure_dark", "set_beam_block", "set_interaction_mode", 
                                 "get_interaction_mode", "min_insertion_loss", "save_config",
                                 "set_lan_address", "get_lan_address", "set_lan_gateway",
                                 "get_lan_gateway", "set_lan_mask", "get_lan_mask",
                                 "set_lan_hostname", "get_lan_hostname"],
                        help="Action to perform")
    parser.add_argument("--value", type=float, help="Value for actions requiring a numeric parameter (e.g., wavelength, attenuation)")
    parser.add_argument("--enable", choices=["true", "false"], 
                        help="Enable/disable for actions like set_power_mode, set_power_leveling, set_beam_block, set_interaction_mode")
    parser.add_argument("--string", help="String value for actions like set_lan_address, set_lan_gateway, set_lan_mask, set_lan_hostname")
    parser.add_argument("--config_file", help="File to save configuration (required for save_config action)")
    return parser.parse_args()

def main():
    args = parse_arguments()
    ova = OVAController(visa_address=args.visa)
    ova.connect()

    # Perform device reset for all actions except queries and save_config to ensure a clean state
    if args.action not in ["get_wavelength", "get_attenuation", "get_power", "get_interaction_mode", 
                           "info", "save_config", "get_version", "get_lan_address", 
                           "get_lan_gateway", "get_lan_mask", "get_lan_hostname"]:
        ova.reset_device()

    # Execute the specified action
    if args.action == "reset":
        pass  # Reset already performed
    elif args.action == "info":
        print("Device Info:", ova.get_device_info())
    elif args.action == "get_version":
        print("System Version:", ova.get_system_version())
    elif args.action == "set_wavelength":
        if args.value is not None:
            ova.set_wavelength(args.value)
        else:
            print("Error: --value is required for set_wavelength")
    elif args.action == "get_wavelength":
        print("Current Wavelength:", ova.get_wavelength())
    elif args.action == "set_attenuation":
        if args.value is not None:
            ova.set_attenuation(args.value)
        else:
            print("Error: --value is required for set_attenuation")
    elif args.action == "get_attenuation":
        print("Current Attenuation:", ova.get_attenuation())
    elif args.action == "set_offset":
        if args.value is not None:
            ova.set_offset(args.value)
        else:
            print("Error: --value is required for set_offset")
    elif args.action == "set_power_mode":
        if args.enable is not None:
            ova.set_absolute_power_mode(args.enable.lower() == "true")
        else:
            print("Error: --enable is required for set_power_mode")
    elif args.action == "set_power":
        if args.value is not None:
            ova.set_power_setpoint(args.value)
        else:
            print("Error: --value is required for set_power")
    elif args.action == "get_power":
        print("Current Power Setpoint:", ova.get_power_setpoint())
    elif args.action == "set_power_leveling":
        if args.enable is not None:
            ova.set_power_leveling(args.enable.lower() == "true")
        else:
            print("Error: --enable is required for set_power_leveling")
    elif args.action == "set_drift_tolerance":
        if args.value is not None:
            ova.set_drift_tolerance(args.value)
        else:
            print("Error: --value is required for set_drift_tolerance")
    elif args.action == "measure_dark":
        ova.measure_dark_current()
    elif args.action == "set_beam_block":
        if args.enable is not None:
            ova.set_beam_block(args.enable.lower() == "true")
        else:
            print("Error: --enable is required for set_beam_block")
    elif args.action == "set_interaction_mode":
        if args.enable is not None:
            ova.set_interaction_mode(args.enable.lower() == "true")
        else:
            print("Error: --enable is required for set_interaction_mode")
    elif args.action == "get_interaction_mode":
        print("Interaction Mode:", ova.get_interaction_mode())
    elif args.action == "min_insertion_loss":
        ova.go_to_min_insertion_loss()
    elif args.action == "save_config":
        if args.config_file is not None:
            ova.save_config(args.config_file)
        else:
            print("Error: --config_file is required for save_config")
    elif args.action == "set_lan_address":
        if args.string is not None:
            ova.set_lan_address(args.string)
        else:
            print("Error: --string is required for set_lan_address")
    elif args.action == "get_lan_address":
        print("LAN Address:", ova.get_lan_address())
    elif args.action == "set_lan_gateway":
        if args.string is not None:
            ova.set_lan_gateway(args.string)
        else:
            print("Error: --string is required for set_lan_gateway")
    elif args.action == "get_lan_gateway":
        print("LAN Gateway:", ova.get_lan_gateway())
    elif args.action == "set_lan_mask":
        if args.string is not None:
            ova.set_lan_mask(args.string)
        else:
            print("Error: --string is required for set_lan_mask")
    elif args.action == "get_lan_mask":
        print("LAN Subnet Mask:", ova.get_lan_mask())
    elif args.action == "set_lan_hostname":
        if args.string is not None:
            ova.set_lan_hostname(args.string)
        else:
            print("Error: --string is required for set_lan_hostname")
    elif args.action == "get_lan_hostname":
        print("LAN Hostname:", ova.get_lan_hostname())

    ova.disconnect()

if __name__ == "__main__":
    main()

"""
Example commands:
python ova_control_usb.py --action reset
python ova_control_usb.py --action info
python ova_control_usb.py --action get_version
python ova_control_usb.py --action set_wavelength --value 1550
python ova_control_usb.py --action get_wavelength
python ova_control_usb.py --action set_attenuation --value 10
python ova_control_usb.py --action set_offset --value 2
python ova_control_usb.py --action set_power_mode --enable true
python ova_control_usb.py --action set_power --value -10
python ova_control_usb.py --action set_power_leveling --enable true
python ova_control_usb.py --action set_drift_tolerance --value 0.2
python ova_control_usb.py --action measure_dark
python ova_control_usb.py --action set_beam_block --enable true
python ova_control_usb.py --action set_interaction_mode --enable false
python ova_control_usb.py --action min_insertion_loss
python ova_control_usb.py --action save_config --config_file config.json
python ova_control_usb.py --action set_lan_address --string 192.168.1.100
python ova_control_usb.py --action get_lan_address
python ova_control_usb.py --action set_lan_gateway --string 192.168.1.1
python ova_control_usb.py --action get_lan_gateway
python ova_control_usb.py --action set_lan_mask --string 255.255.255.0
python ova_control_usb.py --action get_lan_mask
python ova_control_usb.py --action set_lan_hostname --string OVA-Device
python ova_control_usb.py --action get_lan_hostname
"""
