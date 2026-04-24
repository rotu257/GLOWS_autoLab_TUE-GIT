#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python3

import argparse
import contextlib
import os
import re
import socket
import sys

import pyvisa

KNOWN_TCPIP_RESOURCES = [
    "TCPIP::192.168.1.161::5000::SOCKET",
    "TCPIP::192.168.1.10::SOCKET",
    "TCPIP::192.168.1.15::SOCKET",
    "TCPIP::192.168.1.50::5025::SOCKET",
    "TCPIP::192.168.1.51::5025::SOCKET",
    "TCPIP::192.168.1.14::INSTR",
]


@contextlib.contextmanager
def suppress_stderr():
    saved_stderr_fd = None
    devnull_fd = None
    try:
        sys.stderr.flush()
        saved_stderr_fd = os.dup(2)
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, 2)
        yield
    finally:
        if saved_stderr_fd is not None:
            os.dup2(saved_stderr_fd, 2)
            os.close(saved_stderr_fd)
        if devnull_fd is not None:
            os.close(devnull_fd)


def is_tcpip_resource_reachable(resource):
    try:
        match = re.fullmatch(r"TCPIP::([\d.]+)::(\d+)::SOCKET", resource)
        if not match:
            return False

        ip, port = match.groups()
        port = int(port)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            return sock.connect_ex((ip, port)) == 0
    except OSError:
        return False


def get_resources(rm):
    try:
        with suppress_stderr():
            visa_resources = list(rm.list_resources())
    except Exception as exc:
        print(f"Error listing VISA resources: {exc}")
        sys.exit(1)

    tcpip_resources = [
        res for res in KNOWN_TCPIP_RESOURCES if is_tcpip_resource_reachable(res)
    ]

    resources = []
    seen = set()
    for res in [*visa_resources, *tcpip_resources]:
        if res not in seen:
            seen.add(res)
            resources.append(res)

    return resources


def print_resources(resources):
    if not resources:
        print("No VISA resources found!")
        return

    print("\nAvailable VISA resources:")
    for idx, res in enumerate(resources):
        print(f"{idx}: {res}")
    print("Enter a number to select, 'r' to rescan, or 'q' to quit.")


def interactive_select(rm):
    while True:
        resources = get_resources(rm)
        if not resources:
            print("No VISA resources found. Press 'r' to rescan or 'q' to quit.")

        print_resources(resources)

        try:
            user_input = input("Select resource index: ").strip().lower()
        except EOFError:
            print("\nExiting.")
            sys.exit(0)
        except KeyboardInterrupt:
            print("\nExiting.")
            sys.exit(0)

        if user_input in {"q", "quit", "exit"}:
            print("Exiting.")
            sys.exit(0)

        if user_input in {"r", "rescan"}:
            continue

        try:
            selection = int(user_input)
        except ValueError:
            print("Invalid input. Enter a number, 'r', or 'q'.")
            continue

        if 0 <= selection < len(resources):
            return resources[selection]

        print("Invalid selection. Try again.")


def query_resource(rm, resource_str):
    try:
        with rm.open_resource(resource_str) as inst:
            inst.timeout = 10000
            inst.read_termination = "\n"
            inst.write_termination = "\n"
            idn_response = inst.query("*IDN?")
            print("Instrument ID:", idn_response.strip())
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
    except Exception as exc:
        print(f"Error querying resource '{resource_str}': {exc}")


def main():
    parser = argparse.ArgumentParser(
        description="Query the *IDN? of a VISA instrument."
    )
    parser.add_argument(
        "-r",
        "--resource",
        help="Full VISA resource string. If omitted, an interactive selection is provided.",
    )
    args = parser.parse_args()

    try:
        rm = pyvisa.ResourceManager("@py")
    except Exception as exc:
        print(f"Failed to create VISA ResourceManager: {exc}")
        sys.exit(1)

    resource_str = args.resource if args.resource else interactive_select(rm)
    query_resource(rm, resource_str)

def get_resources(rm):
    try:
        with suppress_stderr():
            visa_resources = list(rm.list_resources())
    except Exception as exc:
        print(f"Error listing VISA resources: {exc}")
        sys.exit(1)

    visa_resources = [
        res for res in visa_resources
        if res != "ASRL/dev/ttyS0::INSTR"
    ]

    tcpip_resources = [
        res for res in KNOWN_TCPIP_RESOURCES if is_tcpip_resource_reachable(res)
    ]

    resources = []
    seen = set()
    for res in [*visa_resources, *tcpip_resources]:
        if res not in seen:
            seen.add(res)
            resources.append(res)

    return resources

def build_parser():
    parser = argparse.ArgumentParser(
        description="Scan VISA resources and send SCPI commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  instrument_RM_test
      Scan VISA resources, select one interactively, then send *IDN?

  instrument_RM_test -r GPIB0::5::INSTR
      Open the given resource directly and send *IDN?

  instrument_RM_test -r GPIB0::5::INSTR -c "*IDN?"
      Send one custom SCPI query

  instrument_RM_test -r GPIB0::5::INSTR -c ":SYST:ERR?"
      Send one different SCPI query

  instrument_RM_test -r GPIB0::5::INSTR -C "*RST" "*CLS" "*IDN?" ":SYST:ERR?"
      Send multiple SCPI commands in order

Interactive selection:
  Enter a number to select a resource
  Enter 'r' to rescan
  Enter 'q' to quit
""",
    )
    parser.add_argument(
        "-r",
        "--resource",
        help="Full VISA resource string. If omitted, interactive selection is used.",
    )
    parser.add_argument(
        "-c",
        "--command",
        help="Single SCPI command to send, e.g. '*IDN?' or ':SYST:ERR?'.",
    )
    parser.add_argument(
        "-C",
        "--commands",
        nargs="+",
        help="Multiple SCPI commands to send in order.",
    )
    return parser

if __name__ == "__main__":
    main()
