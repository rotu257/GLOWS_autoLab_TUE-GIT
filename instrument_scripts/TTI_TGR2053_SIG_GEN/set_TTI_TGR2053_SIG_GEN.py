#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
"""
Complete TGR2053 Control Script with Full OOK User-Defined Bit Sequence Support
Upgraded with advanced trigger settings for OOK modulation.
Tested with TGR2053 + U01 Digital Modulation Option
Author: Assistant (based on your original code)
Date: 2026-02-25
"""
import socket
import argparse
import sys
import time
from typing import Optional
import logging
from datetime import datetime
# Default connection settings
DEFAULT_PORT = 5025
DEFAULT_IP = "192.168.1.51" # Change to your instrument's IP
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
class TGR2053:
    """Full-featured class to control Aim-TTi TGR2053 via SCPI over LAN."""
    def __init__(self, ip_address: str = DEFAULT_IP, port: int = DEFAULT_PORT, timeout: float = 10.0):
        self.ip_address = ip_address
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.connect()
    def connect(self) -> None:
        """Establish TCP socket connection."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.ip_address, self.port))
            logger.info(f"Connected to TGR2053 at {self.ip_address}:{self.port}")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            sys.exit(1)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    def write(self, command: str) -> None:
        """Send SCPI command (with newline)."""
        try:
            self.socket.sendall((command + "\n").encode("ascii"))
            logger.debug(f"> {command}")
            time.sleep(0.05) # Small delay for instrument processing
        except Exception as e:
            logger.error(f"Write error: {e}")
            raise
    def read(self) -> str:
        """Read response until newline or timeout."""
        try:
            response = self.socket.recv(4096).decode("ascii").strip()
            if response:
                logger.debug(f"< {response}")
            return response
        except Exception as e:
            logger.warning(f"Read error: {e}")
            return ""
    def query(self, command: str) -> str:
        """Send query and return response."""
        self.write(command)
        return self.read()
    def close(self) -> None:
        if self.socket:
            self.socket.close()
            logger.info("Connection closed")
            self.socket = None
    def identify(self) -> str:
        return self.query("*IDN?")
    def reset(self) -> None:
        self.write("*RST")
        time.sleep(2)
        logger.info("Instrument reset (*RST)")
    def clear_status(self) -> None:
        self.write("*CLS")
        logger.info("Status cleared (*CLS)")
    def set_frequency(self, freq: float, unit: str = "MHZ") -> None:
        unit = unit.upper()
        self.write(f"SOURce:FREQuency:CW {freq} {unit}")
        logger.info(f"Frequency set: {freq} {unit}")
    def set_amplitude(self, level: float, unit: str = "DBM") -> None:
        unit = unit.upper()
        self.write(f"SOURce:POWer:LEVel:IMMediate:AMPLitude {level} {unit}")
        logger.info(f"Amplitude set: {level} {unit}")
    def set_output(self, state: bool) -> None:
        self.write(f"OUTPut:STATe {'ON' if state else 'OFF'}")
        logger.info(f"RF Output: {'ON' if state else 'OFF'}")
    # =====================================================================
    # NEW: Full OOK User-Defined Pattern Support with Advanced Trigger Settings
    # =====================================================================
    def set_ook_user_pattern(self,
                             bit_sequence: str,
                             bitrate: float = 1_000_000,
                             mode: str = "CONTINUOUS",
                             trigger_source: str = "manual",
                             trigger_type: str = "infinite",
                             trigger_mode: str = "bit",
                             trigger_count: int = 1,
                             trigger_rate: Optional[float] = None) -> None:
        """
        Load and enable OOK modulation with a custom bit sequence and advanced trigger settings.
        Args:
            bit_sequence (str): String of '0' and '1' only
            bitrate (float): Bits per second (e.g. 125000, 500000, 1000000)
            mode (str): "CONTINUOUS" or "TRIGGERED"
            trigger_source (str): "internal", "external+ve", "external-ve", "manual", "remote"
            trigger_type (str): "finite" or "infinite"
            trigger_mode (str): "bit" or "block"
            trigger_count (int): Number of triggers for finite type
            trigger_rate (float): Trigger rate in milliseconds for internal source (e.g., 150 for 150ms)
        """
        # --- Validation ---
        bit_sequence = bit_sequence.strip()
        if not bit_sequence:
            logger.error("Empty bit sequence")
            return
        if not all(c in "01" for c in bit_sequence):
            logger.error("Bit sequence must contain only '0' and '1'")
            return
        length = len(bit_sequence)
        if not (1 <= length <= 65536):
            logger.error(f"Pattern length {length} exceeds limit (1–65536)")
            return
        if not (1 <= bitrate <= 1_000_000):
            logger.warning(f"Bitrate {bitrate} bps is outside typical range")
        logger.info(f"Loading OOK user pattern: {length} bits @ {bitrate:,} bps")
        # 2. Define the user pattern using LIST:PRBS (official method for custom sequences)
        bits_str = ",".join(bit_sequence)
        self.write(f":SOURce:LIST:PRBS {length},{bits_str}")
        logger.info(f"Pattern loaded: {bit_sequence[:64]}{'...' if length > 64 else ''}")
        # 3. Set OOK source to USER pattern
        self.write(":SOURce:OOK:SOURce USER")
        logger.info("OOK source → USER pattern")
        # 4. Set internal bit rate
        self.write(f":SOURce:OOK:INTernal:BRATe {int(bitrate)}")
        logger.info(f"OOK bit rate → {bitrate:,} bps")
        # 5. Configure mode
        mode = mode.upper()
        self.write(f":SOURce:OOK:MODE {mode}")
        if mode == "TRIGGERED":
            # Map trigger source
            trig_map = {
                "internal": "INTernal",
                "external+ve": "EXTPositive",
                "external-ve": "EXTNegative",
                "manual": "MANual",
                "remote": "BUS"
            }
            trig = trig_map.get(trigger_source.lower(), "MANual")
            self.write(f":SOURce:OOK:TRIGger:SOURce {trig}")
            # Trigger type
            trig_type = trigger_type.upper()
            self.write(f":SOURce:OOK:TRIGger:TYPE {trig_type[:3] + trig_type[3:].capitalize()}")  # FINite or INFinite
            # Trigger mode
            self.write(f":SOURce:OOK:TRIGger:MODE {trigger_mode.upper()}")
            # Count for finite
            if trig_type == "FINITE":
                self.write(f":SOURce:OOK:TRIGger:COUNt {trigger_count}")
            # Rate for internal
            if trig == "INTernal":
                if trigger_rate is None:
                    logger.error("Internal trigger source requires trigger_rate")
                    return
                self.write(f":SOURce:OOK:TRIGger:RATE {trigger_rate}MS")
            logger.info(f"OOK mode → TRIGGERED (source: {trig}, type: {trig_type}, mode: {trigger_mode.upper()}, count: {trigger_count if trig_type == 'FINITE' else 'N/A'}, rate: {trigger_rate}MS if internal)")
        else:
            logger.info("OOK mode → CONTINUOUS (looping)")
        # 6. Enable OOK modulation and overall modulation
        self.write(":SOURce:MODulation:STATe ON")
        self.write(":SOURce:OOK:STATe ON")
        logger.info("OOK modulation ENABLED")
        # Optional: Enable rear-panel diagnostic outputs
        self.write(":SOURce:OOK:MOD:OUTPut ON") # Raw bit stream on MOD OUT
        self.write(":SOURce:OOK:SYNCOUT OFF") # Bit clock on SYNC OUT (corrected from original)
        logger.info("MOD OUT (bit stream) and SYNC OUT (bit clock) enabled")
    def trigger_ook(self) -> None:
        """Send manual trigger (only works in TRIGGERED mode)."""
        self.write(":TRIGger IMMediate")
        logger.info("Manual OOK trigger sent")
    def log_properties(self, filepath: str) -> None:
        """Append current settings to a log file."""
        try:
            freq = self.query("SOURce:FREQuency:CW?")
            ampl = self.query("SOURce:POWer:LEVel:IMMediate:AMPLitude?")
            unit = self.query("SOURce:POWer:LEVel:IMMediate:UNIT?") or "dBm"
            ook_state = self.query("SOURce:OOK:STATe?")
            bitrate = self.query("SOURce:OOK:INTernal:BRATe?")
            output = self.query("OUTPut:STATe?")
            trig_source = self.query("SOURce:OOK:TRIGger:SOURce?") if ook_state == "1" else "N/A"
            trig_type = self.query("SOURce:OOK:TRIGger:TYPE?") if ook_state == "1" else "N/A"
            trig_mode = self.query("SOURce:OOK:TRIGger:MODE?") if ook_state == "1" else "N/A"
            trig_count = self.query("SOURce:OOK:TRIGger:COUNt?") if ook_state == "1" else "N/A"
            trig_rate = self.query("SOURce:OOK:TRIGger:RATE?") if ook_state == "1" else "N/A"
            with open(filepath, "a") as f:
                f.write(f"{datetime.now()} | "
                        f"Freq: {freq} Hz | "
                        f"Level: {ampl} {unit} | "
                        f"OOK: {ook_state} | "
                        f"Bitrate: {bitrate} bps | "
                        f"RF Out: {output} | "
                        f"Trig Source: {trig_source} | "
                        f"Trig Type: {trig_type} | "
                        f"Trig Mode: {trig_mode} | "
                        f"Trig Count: {trig_count} | "
                        f"Trig Rate: {trig_rate}\n")
            logger.info(f"Settings logged to {filepath}")
        except Exception as e:
            logger.error(f"Logging failed: {e}")
# =============================================================================
# Main CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="TGR2053 Control with Full OOK User Pattern Support and Advanced Triggers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
# 1) Basic CW signal at 80 MHz, -10 dBm, RF ON
Set simple CW carrier:
    python set_TTI_TGR2053_SIG_GEN.py -f 80 -fu MHZ -a -10 -au DBM -o ON

# 2) Just query the instrument identity
Read *IDN?:
    python set_TTI_TGR2053_SIG_GEN.py --idn

# 3) Reset the instrument and clear status
Reset and clear error/status registers:
    python set_TTI_TGR2053_SIG_GEN.py --reset -cls

# 4) Turn RF output OFF (leave other settings unchanged)
Disable RF output:
    python set_TTI_TGR2053_SIG_GEN.py -o OFF

# 5) Log signal properties to a file
Log signal properties to a file:
    python set_TTI_TGR2053_SIG_GEN.py -f 80 -fu MHZ -a -10 -au DBM --log output.txt

# 6) Continuous OOK at 433.92 MHz with custom pattern
Continuous OOK, 125 kbps, repeating user pattern:
    python set_TTI_TGR2053_SIG_GEN.py -f 433.92 -fu MHZ -a -10 -au DBM -o ON \
        --ook --bitseq 1010101011110000111100001111000010101010 --bitrate 125000

# 7) Triggered OOK "wake-up" packet with advanced settings
Configure triggered OOK at 500 kbps, finite block mode, external +ve trigger, count 5:
    python set_TTI_TGR2053_SIG_GEN.py -f 868.3 -fu MHZ -a -5 -au DBM -o ON \
        --ook --bitseq 11001100111100001111 --bitrate 500000 --ook-mode triggered \
        --trigger-source external+ve --trigger-type finite --trigger-mode block --trigger-count 5
Later, trigger occurs on external signal.

# 8) Triggered with internal timer, infinite bit mode
    python set_TTI_TGR2053_SIG_GEN.py -f 868.3 -fu MHZ -a -5 -au DBM -o ON \
        --ook --bitseq 11001100111100001111 --bitrate 500000 --ook-mode triggered \
        --trigger-source internal --trigger-type infinite --trigger-mode bit --trigger-rate 150

# 9) Send manual trigger (for manual or remote triggered mode)
    python set_TTI_TGR2053_SIG_GEN.py --ook-trigger

# 10) Change only frequency and power, preserve RF state
Retune frequency and level without touching output state:
    python set_TTI_TGR2053_SIG_GEN.py -f 2.45 -fu GHZ -a -3 -au DBM
    
# 11) Use a different IP / port
Control a unit at custom IP / port:
    python set_TTI_TGR2053_SIG_GEN.py -i 192.168.0.55 -p 5025 -f 100 -fu MHZ -a 0 -au DBM -o ON
        """
    )
    # Connection
    parser.add_argument("-i", "--ip", default=DEFAULT_IP, help="Instrument IP address")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help="Port (default 5025)")
    # Basic settings
    parser.add_argument("-f", "--freq", type=float, help="Frequency value")
    parser.add_argument("-fu", "--freq-unit", default="MHZ", choices=["HZ", "KHZ", "MHZ", "GHZ"])
    parser.add_argument("-a", "--ampl", type=float, help="Amplitude")
    parser.add_argument("-au", "--ampl-unit", default="DBM", choices=["DBM", "DBUV", "UV", "MV"])
    parser.add_argument("-o", "--output", choices=["ON", "OFF"], help="RF output state")
    parser.add_argument("--reset", action="store_true", help="Reset instrument")
    parser.add_argument("--idn", action="store_true", help="Print *IDN? response")
    parser.add_argument("-cls", "--clear_status", action="store_true",
                        help="Clear error queue and status registers")
    # OOK User Pattern
    parser.add_argument("--ook", action="store_true", help="Enable OOK with custom bit sequence")
    parser.add_argument("--bitseq", type=str, help="Bit sequence (string of 0s and 1s only)")
    parser.add_argument("--bitrate", type=float, default=1_000_000, help="Bit rate in bps (default 1e6)")
    parser.add_argument("--ook-mode", choices=["continuous", "triggered"], default="continuous")
    # Advanced Trigger Settings
    parser.add_argument("--trigger-source", choices=["internal", "external+ve", "external-ve", "manual", "remote"], default="manual",
                        help="Trigger source for triggered mode")
    parser.add_argument("--trigger-type", choices=["finite", "infinite"], default="infinite",
                        help="Trigger type (finite or infinite)")
    parser.add_argument("--trigger-mode", choices=["bit", "block"], default="bit",
                        help="Trigger mode (bit or block)")
    parser.add_argument("--trigger-count", type=int, default=1, help="Trigger count for finite type")
    parser.add_argument("--trigger-rate", type=float, help="Trigger rate in ms for internal source")
    parser.add_argument("--ook-trigger", action="store_true", help="Send manual trigger (triggered mode only)")
    # Logging
    parser.add_argument("--log", type=str, help="Log current settings to file")
    args = parser.parse_args()
    # Basic validation
    if args.ook and not args.bitseq:
        parser.error("--ook requires --bitseq")
    if args.ook_mode == "triggered" and args.trigger_source == "internal" and args.trigger_rate is None:
        parser.error("--trigger-source internal requires --trigger-rate")
    with TGR2053(ip_address=args.ip, port=args.port) as tgr:
        if args.idn:
            print(tgr.identify())
            return
        if args.reset:
            tgr.reset()
            time.sleep(3)
        if args.clear_status:
            tgr.clear_status()
        if args.freq:
            tgr.set_frequency(args.freq, args.freq_unit)
        if args.ampl:
            tgr.set_amplitude(args.ampl, args.ampl_unit)
        if args.output:
            tgr.set_output(args.output == "ON")
        if args.ook:
            tgr.set_ook_user_pattern(
                bit_sequence=args.bitseq,
                bitrate=args.bitrate,
                mode=args.ook_mode.upper(),
                trigger_source=args.trigger_source,
                trigger_type=args.trigger_type,
                trigger_mode=args.trigger_mode,
                trigger_count=args.trigger_count,
                trigger_rate=args.trigger_rate
            )
            # Auto-enable RF output when OOK is configured
            tgr.set_output(True)
        if args.ook_trigger:
            tgr.trigger_ook()
        if args.log:
            tgr.log_properties(args.log)
        # Final status
        if any([args.freq, args.ampl, args.output, args.ook]):
            logger.info("Configuration complete")
if __name__ == "__main__":
    main()
