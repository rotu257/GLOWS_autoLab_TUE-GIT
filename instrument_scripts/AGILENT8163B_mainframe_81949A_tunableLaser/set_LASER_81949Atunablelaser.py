#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
"""
8163B + 81949A Tunable Laser Controller (extensible skeleton)

Key fix vs earlier version:
- Laser emission enable/disable is typically via :...:POWer:STATe (not :OUTPut:STATe).
- This implementation uses POWer:STATe as primary and OUTPut:STATe as fallback.

Examples:
  python laser8163b.py idn
  python laser8163b.py status
  python laser8163b.py set-wl 1550 --unit nm
  python laser8163b.py set-pwr 6.0
  python laser8163b.py output on
  python laser8163b.py errors
  python laser8163b.py scpi ":SOURce1:CHANnel1:POWer:STATe?"
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
import time
from typing import Optional, Sequence

import pyvisa


DEFAULT_ADDRESS = "GPIB0::11::INSTR"
DEFAULT_TIMEOUT_MS = 30_000


@dataclasses.dataclass(frozen=True)
class LaserPath:
    """Identifies the laser output in the mainframe."""
    slot: int = 1
    channel: int = 1


@dataclasses.dataclass
class LaserStatus:
    idn: str
    wavelength_m: Optional[float] = None
    power_dbm: Optional[float] = None
    output_on: Optional[bool] = None
    last_error: Optional[str] = None


class VisaInstrument:
    """Tiny wrapper around a pyvisa resource."""

    def __init__(self, address: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
        self.address = address
        self.timeout_ms = timeout_ms
        self._rm: Optional[pyvisa.ResourceManager] = None
        self._inst = None

    def open(self) -> "VisaInstrument":
        self._rm = pyvisa.ResourceManager()
        self._inst = self._rm.open_resource(self.address)
        self._inst.timeout = self.timeout_ms
        self._inst.write_termination = "\n"
        self._inst.read_termination = "\n"
        return self

    def close(self) -> None:
        try:
            if self._inst is not None:
                self._inst.close()
        finally:
            self._inst = None
            if self._rm is not None:
                try:
                    self._rm.close()
                except Exception:
                    pass
                self._rm = None

    def write(self, cmd: str) -> None:
        if self._inst is None:
            raise RuntimeError("Instrument not open")
        self._inst.write(cmd)

    def query(self, cmd: str) -> str:
        if self._inst is None:
            raise RuntimeError("Instrument not open")
        return str(self._inst.query(cmd))

    def query_float(self, cmd: str) -> float:
        return float(self.query(cmd).strip())

    def query_int(self, cmd: str) -> int:
        return int(self.query(cmd).strip())


class Laser8163B:
    """
    High-level API for 8163B mainframe controlling a tunable laser module.
    Keep all SCPI in this class for easy extension.
    """

    def __init__(self, visa: VisaInstrument, path: LaserPath = LaserPath()) -> None:
        self.visa = visa
        self.path = path

    def _src(self) -> str:
        return f":SOURce{self.path.slot}:CHANnel{self.path.channel}"

    # ---- base ----

    def idn(self) -> str:
        return self.visa.query("*IDN?").strip()

    def cls(self) -> None:
        self.visa.write("*CLS")

    def rst(self, settle_s: float = 15.0) -> None:
        self.visa.write("*RST")
        time.sleep(settle_s)
        self.cls()

    # ---- errors ----

    def read_error(self) -> str:
        return self.visa.query("SYST:ERR?").strip()

    def drain_errors(self, max_reads: int = 50, delay_s: float = 0.05) -> list[str]:
        errors: list[str] = []
        for _ in range(max_reads):
            err = self.read_error()
            if err.startswith("0,"):
                break
            errors.append(err)
            time.sleep(delay_s)
        return errors

    # ---- laser controls ----

    def get_wavelength_m(self) -> float:
        return self.visa.query_float(f"{self._src()}:WAVelength?")

    def set_wavelength_m(self, wavelength_m: float) -> None:
        self.visa.write(f"{self._src()}:WAVelength {wavelength_m}")

    def get_power_dbm(self) -> float:
        self.visa.write(f"{self._src()}:POWer:UNIT DBM")
        return self.visa.query_float(f"{self._src()}:POWer?")

    def set_power_dbm(self, power_dbm: float) -> None:
        self.visa.write(f"{self._src()}:POWer:UNIT DBM")
        self.visa.write(f"{self._src()}:POWer {power_dbm}")

    def get_output(self) -> bool:
        # Preferred for tunable laser modules in 8163B systems
        try:
            v = self.visa.query(f"{self._src()}:POWer:STATe?").strip().upper()
            return v in {"1", "ON"}
        except Exception:
            v = self.visa.query(f"{self._src()}:OUTPut:STATe?").strip().upper()
            return v in {"1", "ON"}

    def set_output(self, on: bool) -> None:
        state_num = "1" if on else "0"
        try:
            self.visa.write(f"{self._src()}:POWer:STATe {state_num}")
            return
        except Exception:
            self.visa.write(f"{self._src()}:OUTPut:STATe {'ON' if on else 'OFF'}")

    def set_output_verify(
        self,
        on: bool,
        timeout_s: float = 5.0,
        poll_s: float = 0.2,
    ) -> bool:
        self.set_output(on)
        end = time.time() + timeout_s
        target = bool(on)
        while time.time() < end:
            try:
                if self.get_output() == target:
                    return True
            except Exception:
                pass
            time.sleep(poll_s)
        return False

    # ---- status ----

    def status(self) -> LaserStatus:
        s = LaserStatus(idn=self.idn())
        try:
            s.wavelength_m = self.get_wavelength_m()
        except Exception:
            pass
        try:
            s.power_dbm = self.get_power_dbm()
        except Exception:
            pass
        try:
            s.output_on = self.get_output()
        except Exception:
            pass
        try:
            s.last_error = self.read_error()
        except Exception:
            pass
        return s

    # ---- raw SCPI ----

    def scpi(self, cmd: str) -> str:
        cmd = cmd.strip()
        if cmd.endswith("?"):
            return self.visa.query(cmd).strip()
        self.visa.write(cmd)
        return "OK"


def wl_to_m(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "m":
        return value
    if u == "nm":
        return value * 1e-9
    if u in {"um", "µm"}:
        return value * 1e-6
    raise ValueError(f"Unsupported wavelength unit: {unit} (use m/nm/um)")


def wl_from_m(value_m: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "m":
        return value_m
    if u == "nm":
        return value_m * 1e9
    if u in {"um", "µm"}:
        return value_m * 1e6
    raise ValueError(f"Unsupported wavelength unit: {unit} (use m/nm/um)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Agilent/Keysight 8163B + 81949A laser control (extensible skeleton)"
    )
    p.add_argument("--address", default=DEFAULT_ADDRESS, help=f"VISA address (default: {DEFAULT_ADDRESS})")
    p.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS, help="VISA timeout in ms")
    p.add_argument("--slot", type=int, default=1, help="Laser module slot (default: 1)")
    p.add_argument("--channel", type=int, default=1, help="Laser channel (default: 1)")

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("idn", help="Query *IDN?")

    sp = sub.add_parser("status", help="Query wavelength/power/output and last error")
    sp.add_argument("--wl-unit", default="nm", choices=["m", "nm", "um"], help="Display wavelength unit")

    sub.add_parser("errors", help="Drain and print error queue")

    sp = sub.add_parser("set-wl", help="Set wavelength")
    sp.add_argument("value", type=float, help="Wavelength value")
    sp.add_argument("--unit", default="nm", choices=["m", "nm", "um"], help="Input unit (default nm)")

    sp = sub.add_parser("get-wl", help="Get wavelength")
    sp.add_argument("--unit", default="nm", choices=["m", "nm", "um"], help="Output unit (default nm)")

    sp = sub.add_parser("set-pwr", help="Set power (dBm)")
    sp.add_argument("dbm", type=float, help="Power in dBm")

    sub.add_parser("get-pwr", help="Get power (dBm)")

    sp = sub.add_parser("output", help="Set laser output ON/OFF (uses POWer:STATe primary)")
    sp.add_argument("state", choices=["on", "off"], help="on/off")
    sp.add_argument("--verify", action="store_true", help="Poll state until it latches or times out")
    sp.add_argument("--verify-timeout-s", type=float, default=5.0, help="Verify timeout seconds (default 5)")

    sp = sub.add_parser("scpi", help="Send raw SCPI (query or write)")
    sp.add_argument("command", help='Example: "*IDN?" or ":SOURce1:CHANnel1:WAVelength 1.55e-6"')

    sp = sub.add_parser("reset", help="Send *RST then *CLS")
    sp.add_argument("--settle-s", type=float, default=15.0, help="Seconds to wait after reset (default 15)")

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    visa = VisaInstrument(address=args.address, timeout_ms=args.timeout_ms)
    path = LaserPath(slot=args.slot, channel=args.channel)

    try:
        visa.open()
        laser = Laser8163B(visa, path=path)

        if args.cmd == "idn":
            print(laser.idn())
            return 0

        if args.cmd == "reset":
            laser.rst(settle_s=float(args.settle_s))
            print("OK")
            return 0

        if args.cmd == "status":
            st = laser.status()
            wl = None if st.wavelength_m is None else wl_from_m(st.wavelength_m, args.wl_unit)
            wl_str = "n/a" if wl is None else f"{wl:.6f} {args.wl_unit}"
            pwr_str = "n/a" if st.power_dbm is None else f"{st.power_dbm:.4f} dBm"
            out_str = "n/a" if st.output_on is None else ("ON" if st.output_on else "OFF")
            err_str = "n/a" if st.last_error is None else st.last_error
            print(f"IDN: {st.idn}")
            print(f"Wavelength: {wl_str}")
            print(f"Power: {pwr_str}")
            print(f"Output: {out_str}")
            print(f"Last error: {err_str}")
            return 0

        if args.cmd == "errors":
            errs = laser.drain_errors()
            if not errs:
                print("0,No error")
            else:
                for e in errs:
                    print(e)
            return 0

        if args.cmd == "set-wl":
            laser.set_wavelength_m(wl_to_m(float(args.value), args.unit))
            print("OK")
            return 0

        if args.cmd == "get-wl":
            wl_m = laser.get_wavelength_m()
            print(f"{wl_from_m(wl_m, args.unit):.9f} {args.unit}")
            return 0

        if args.cmd == "set-pwr":
            laser.set_power_dbm(float(args.dbm))
            print("OK")
            return 0

        if args.cmd == "get-pwr":
            print(f"{laser.get_power_dbm():.4f} dBm")
            return 0

        if args.cmd == "output":
            want_on = args.state == "on"
            if args.verify:
                ok = laser.set_output_verify(want_on, timeout_s=float(args.verify_timeout_s))
                if not ok:
                    print("FAILED (state did not latch). Last error:", laser.read_error(), file=sys.stderr)
                    return 3
                print("OK")
                return 0
            laser.set_output(want_on)
            print("OK")
            return 0

        if args.cmd == "scpi":
            print(laser.scpi(args.command))
            return 0

        raise RuntimeError(f"Unknown command: {args.cmd}")

    except pyvisa.VisaIOError as e:
        print(f"VISA error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        visa.close()


if __name__ == "__main__":
    raise SystemExit(main())
