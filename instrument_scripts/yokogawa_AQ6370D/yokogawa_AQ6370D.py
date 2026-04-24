#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
"""
Yokogawa instrument interface for spectral data acquisition.
"""

import argparse
import socket
import sys
import time
import os
import subprocess
import numpy as np

HOSTNAME = "192.168.108.5"
PORT = 10001
BUFFER_SIZE = 2048
MAX_DATA_LENGTH = 100000

class Yokogawa:
    def __init__(self, filename=None, query=None, command=None, host=HOSTNAME,
                 force=False, save=True, trigger=False):
        self.host = host
        self.force = force
        self.save = save

        # Establish connection
        try:
            self.sock = socket.create_connection((self.host, PORT))
        except socket.error as e:
            print(f"Error connecting to {self.host}:{PORT} - {e}")
            sys.exit(1)

        # Authentication
        self.send('OPEN "anonymous"')
        ans = self.recv()
        if ans != 'AUTHENTICATE CRAM-MD5.':
            print("Problem with authentication:", ans)
            sys.exit(1)
        self.send(" ")
        ans = self.recv()
        if ans != 'ready':
            print("Problem with authentication:", ans)
            sys.exit(1)

        if query:
            print(f'\nAnswer to query: {query}')
            rep = self.query(query)
            print(rep, '\n')
            sys.exit(0)
        if command:
            print(f'\nExecuting command: {command}')
            self.send(command)
            print('\n')
            sys.exit(0)

        if trigger:
            self.send('*TRG')
            delay = 0.1
            while self.query(':STATUS:OPER:COND?') != '1':
                time.sleep(delay)
                print(f'Waiting for trigger: {delay:.1f}s')
                delay += 0.1

        if filename:
            lambd, amp = self.get_data()
            # Convert to floats
            try:
                lambd = list(map(float, lambd))
                amp = list(map(float, amp))
            except ValueError as e:
                print("Error parsing data to floats:", e)
                sys.exit(1)

            if self.save:
                temp_filename = f"{filename}_YOKO.txt"
                if os.path.exists(temp_filename) and not self.force:
                    print(f'\nFile {temp_filename} already exists. Use --force to overwrite.\n')
                    sys.exit(1)
                # Save columns: wavelength, amplitude
                data = np.column_stack((lambd, amp))
                np.savetxt(
                    temp_filename,
                    data,
                    fmt='%.6e',
                    delimiter='\t',
                    header='Wavelength\tAmplitude',
                    comments=''
                )
                print(f"Data saved to {temp_filename}")

    def get_data(self):
        x_raw = self.query(':TRAC:DATA:X? TRA', length=MAX_DATA_LENGTH)
        y_raw = self.query(':TRAC:DATA:Y? TRA', length=MAX_DATA_LENGTH)
        return x_raw.split(','), y_raw.split(',')

    def send(self, msg):
        if not msg.endswith('\n'):
            msg += '\n'
        try:
            self.sock.sendall(msg.encode('ascii'))
        except socket.error as e:
            print(f"Error sending message: {e}")
            sys.exit(1)

    def recv(self, length=BUFFER_SIZE):
        data = b''
        while not data.endswith(b'\r\n'):
            try:
                chunk = self.sock.recv(length)
            except socket.error as e:
                print(f"Error receiving data: {e}")
                sys.exit(1)
            if not chunk:
                break
            data += chunk
        return data.rstrip(b'\r\n').decode('ascii')

    def query(self, msg, length=BUFFER_SIZE):
        """Send a command and return the response."""
        self.send(msg)
        return self.recv(length)

    def makesweep(self):
        """Trigger a single sweep."""
        self.mode('1')
        self.send('INIT')

    def mode(self, mode=None):
        """Set or query sweep mode. Returns current mode."""
        if mode is not None:
            self.send(f'INIT:SMOD {mode}')
        return self.query('INIT:SMOD?')


def main():
    parser = argparse.ArgumentParser(
        description="Record spectrum from Yokogawa instrument and save to file."
    )
    parser.add_argument('-c', '--command', help="Send a command to the instrument", dest='command')
    parser.add_argument('-q', '--query', help="Query the instrument", dest='query')
    parser.add_argument('-o', '--output', help="Base filename for saving data", dest='filename')
    parser.add_argument('-F', '--force', action='store_true', help="Overwrite existing files", dest='force')
    parser.add_argument('-i', '--ip', help="Instrument IP address", default=HOSTNAME, dest='ip_address')
    parser.add_argument('-t', '--trigger', action='store_true',
                        help="Trigger a sweep before acquiring data", dest='trigger')

    args = parser.parse_args()

    Yokogawa(
        filename=args.filename,
        query=args.query,
        command=args.command,
        host=args.ip_address,
        force=args.force,
        trigger=args.trigger
    )

if __name__ == "__main__":
    main()
'''
usage:

yokogawa_AQ6370D.py -o filename

yokogawa_AQ6370D.py -o filename -F

'''