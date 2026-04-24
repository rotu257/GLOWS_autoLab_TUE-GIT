#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

import serial
import serial.tools.list_ports
import time
import os
from optparse import OptionParser
import uuid
import datetime

class BCB4Controller:
    def __init__(self, port=None, address=1, baudrate=9600, retries=3):
        self.address = address
        self.retries = retries
        self.ser = None
        self.port = port

        if port:
            # Try user-specified port first with multiple addresses
            self.ser = self._try_connect(port)
            if not self.ser:
                print(f"Failed to connect to specified port {port}. Attempting auto-detection...")
                self.ser, self.port, self.address = self._auto_detect_port()
        else:
            # Auto-detect port
            self.ser, self.port, self.address = self._auto_detect_port()

        if not self.ser:
            raise Exception("No functional COM port found for BCB-4 communication. Ensure the device is connected and permissions are set (e.g., 'sudo chmod 666 /dev/ttyUSB0').")

    def _try_connect(self, port, addresses=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]):
        """Attempt to connect to a specific port and verify with RFW command across multiple addresses."""
        try:
            ser = serial.Serial(
                port=port,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            time.sleep(1)  # Wait for serial connection to stabilize
            for addr in addresses:
                try:
                    ser.write(f"RFW|{addr}|CR/LF\r\n".encode())
                    time.sleep(0.1)
                    response = ser.readline().decode().strip()
                    if response:
                        print(f"Successfully connected to BCB-4 on {port} with address {addr}")
                        self.address = addr  # Update address
                        return ser
                except serial.SerialException as e:
                    print(f"Address {addr} on {port}: Serial error - {e}")
            ser.close()
        except serial.SerialException as e:
            print(f"Failed to connect on {port}: {e}")
            if 'ser' in locals() and ser.is_open:
                ser.close()
        return None

    def _auto_detect_port(self):
        """Detect available serial ports and find one that communicates with BCB-4."""
        # Filter for common USB serial ports
        ports = [port.device for port in serial.tools.list_ports.comports() if 'USB' in port.device or 'ttyS' in port.device]
        if not ports:
            print("No serial ports found. Check BCB-4 connection and USB-to-RS485 adapter.")
            return None, None, self.address

        print(f"Detected serial ports: {ports}")
        for port in ports:
            ser = self._try_connect(port)
            if ser:
                return ser, port, self.address
        print("No ports responded to BCB-4 communication. Try specifying a port with -r or check permissions.")
        return None, None, self.address

    def send_command(self, command):
        """Send a command to the BCB-4 and return the response."""
        if not self.ser or not self.ser.is_open:
            raise Exception("Serial port not open.")
        full_command = f"{command}{self.address}|CR/LF\r\n".encode()
        for attempt in range(self.retries):
            try:
                self.ser.write(full_command)
                time.sleep(0.1)  # Wait for response
                response = self.ser.readline().decode().strip()
                if response:
                    return response
                print(f"Attempt {attempt + 1}: No response received.")
            except serial.SerialException as e:
                print(f"Attempt {attempt + 1}: Serial error - {e}")
            time.sleep(0.5)
        raise Exception("Failed to get response after retries")

    def query(self, query_str):
        """Handle query commands (e.g., RFW, READ|ADD|V)."""
        if query_str.startswith("READ|") or query_str == "RFW":
            return self.send_command(query_str + "|")
        else:
            raise ValueError("Unsupported query command. Use RFW, READ|ADD|V, READ|ADD|V/PI, READ|ADD|DSF, or READ|ADD|S")

    def execute_command(self, command_str):
        """Execute a command (e.g., SET[ADD]M:X, RESET)."""
        valid_commands = ["RESET", "SETADD", "SETM", "SETV", "SETOFS", "JUMP"]
        command_prefix = command_str.split("|")[0] if "|" in command_str else command_str
        if any(command_prefix.startswith(cmd) for cmd in valid_commands):
            return self.send_command(command_str + "|")
        else:
            raise ValueError("Unsupported command. Refer to Appendix B of the BCB-4 manual.")

    def read_optical_power(self):
        """Read optical input DAC value and calculate optical power."""
        response = self.send_command(f"READ|{self.address}|S|")
        try:
            dac_value = int(response.split(",")[0])  # Adjust based on actual response format
            optical_power = dac_value * 1e-6  # Placeholder coefficient
            return optical_power
        except (ValueError, IndexError):
            raise Exception("Failed to parse optical power from status response")

    def close(self):
        """Close the serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()

def main():
    usage = """usage: %prog [options]

    To save a measurement to a file:
        python bcb4_control.py -o measurement_file

    To query the instrument identification:
        python bcb4_control.py -q "RFW"

    To execute a custom RS485 command:
        python bcb4_control.py -c "SETM:1"

    To reset the device:
        python bcb4_control.py -c "RESET"
    """
    parser = OptionParser(usage=usage)
    parser.add_option("-q", "--query", type="str", dest="query", default=None,
                      help="RS485 query string to send to the BCB-4 (e.g., 'RFW', 'READ|ADD|V').")
    parser.add_option("-c", "--command", type="str", dest="command", default=None,
                      help="RS485 command string to send to the BCB-4 (e.g., 'SETM:1').")
    parser.add_option("-r", "--resource", type="str", dest="resource", default=None,
                      help="Serial port resource string (e.g., '/dev/ttyUSB0'). If not specified, auto-detects.")
    parser.add_option("-o", "--filename", type="str", dest="filename", default=None,
                      help="Name of the output file to save the measurement data.")
    parser.add_option("-F", "--force", action="store_true", dest="force", default=False,
                      help="Allow overwriting the output file if it already exists.")
    parser.add_option("--retries", type="int", dest="retries", default=3,
                      help="Number of retry attempts for invalid measurements (default: 3).")
    (options, args) = parser.parse_args()

    # Initialize BCB-4 controller with auto-detection or specified port
    try:
        controller = BCB4Controller(port=options.resource, retries=options.retries)
        print(f"Using port: {controller.port}, Address: {controller.address}")
    except Exception as e:
        print(f"Error initializing controller: {e}")
        return

    try:
        if options.query:
            result = controller.query(options.query)
            print(f"Query result: {result}")

        if options.command:
            result = controller.execute_command(options.command)
            print(f"Command result: {result}")

        if options.filename:
            if os.path.exists(options.filename) and not options.force:
                print(f"Error: File '{options.filename}' exists. Use -F to overwrite.")
                return
            optical_power = controller.read_optical_power()
            timestamp = datetime.datetime.now().isoformat()
            measurement_data = f"Timestamp: {timestamp}\nOptical Power (W): {optical_power}\n"
            with open(options.filename, "w") as f:
                f.write(measurement_data)
            print(f"Measurement saved to {options.filename}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        controller.close()

if __name__ == "__main__":
    main()

'''
    Query Commands
Query commands retrieve information from the BCB-4. They are executed using the -q option in the script.

Read Firmware Revision
Command: RFW
Description: Retrieves the firmware revision of the BCB-4.
Example: python bcb4_control.py -q "RFW"
Expected Response: Firmware version (e.g., "1.0.0").

Read Current Bias Voltage DAC Value
Command: READ|ADD|V
Description: Retrieves the current bias voltage DAC value (0 to 16383).
Example: python bcb4_control.py -q "READ|1|V"
Expected Response: DAC value (e.g., "10000").

Read Vpi DAC Value
Command: READ|ADD|V/PI
Description: Retrieves the Vpi DAC value.
Example: python bcb4_control.py -q "READ|1|V/PI"
Expected Response: Vpi DAC value (e.g., "5000").

Read Bias Point Offset Value (Single Mode)
Command: READ|ADD|DSF|X (X = 1, 2, 3, or 4)
Description: Retrieves the bias point offset value for a specific bias mode (1: Q+, 2: Q-, 3: MAX, 4: MIN).
Examples:
Q+ offset: python bcb4_control.py -q "READ|1|DSF|1"
Q- offset: python bcb4_control.py -q "READ|1|DSF|2"
MAX offset: python bcb4_control.py -q "READ|1|DSF|3"
MIN offset: python bcb4_control.py -q "READ|1|DSF|4"
Expected Response: Offset value (e.g., "+0039").

Read All Bias Point Offset Values
Command: READ|ADD|DSF
Description: Retrieves the bias point offset values for all four bias modes (Q+, Q-, MAX, MIN) line by line.
Example: python bcb4_control.py -q "READ|1|DSF"
Expected Response: Four lines, each with an offset value (e.g., "+0039\n-0020\n+0000\n-0010").

Read Device Status
Command: READ|ADD|S
Description: Retrieves device status information, including optical input DAC value.
Example: python bcb4_control.py -q "READ|1|S"
Expected Response: Status data (format not specified in manual, may include optical input DAC value).
    
    
'''