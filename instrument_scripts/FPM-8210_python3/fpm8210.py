#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python

from optparse import OptionParser
import sys
import pyvisa as visa
import subprocess as sp
import gpib

class fpm8210:
    def __init__(self, query=None, command=None, FORCE=False, filename=None, SAVE=True):
        rm = visa.ResourceManager()
        gpib = rm.open_resource('GPIB0::1::INSTR')
        gpib.write('ZERO')
        gpib.write('Filter FAST')
        gpib.write('RANGE:AUTO 1')
        gpib.write('WAVE 980')

        if query:
            print('\nAnswer to query:', query)
            self.write(query+'\n')
            rep = self.read()
            print(rep, '\n')
            sys.exit()
        elif command:
            self.command = command
            print('\nExecuting command', self.command)
            self.scope.write(self.command)
            print('\n')
            sys.exit()

        if filename:
            self.amp = self.get_power()

        if SAVE:
            temp = sp.getoutput('ls').splitlines()
            temp_filename = filename + 'fpm8210'
            if temp_filename in temp:
                print(f'\nFile {temp_filename} already exists, change filename or remove the old file\n')
                sys.exit()

            with open(filename + '_fpm8210', 'w') as f:
                f.write(self.data)

    def get_power(self, filename='test_save_file_', PLOT=False, typ='BYTE', SAVE=False):
        print("ACQUIRING...")
        gpib.write(self, 'POWER?')
        self.data = gpib.read(self.scope, 1000)
        print("CHEERS!!!")
        return self.data

if __name__ == '__main__':
    usage = """usage: %prog [options] arg

       EXAMPLES:

           get_fpm8210 -o filename
               """
    parser = OptionParser(usage)
    parser.add_option("-q", "--query", type="str", dest="com", default=None, help="Set the query to use.")
    parser.add_option("-c", "--command", type="str", dest="com", default=None, help="Set the command to execute.")
    parser.add_option("-i", "--gpib_port", type="str", dest="gpib_port", default='1', help="Set the GPIB port to use.")
    parser.add_option("-o", "--filename", type="string", dest="filename", default=None, help="Set the name of the output file")
    parser.add_option("-F", "--force", type="string", dest="force", default=None, help="Allows overwriting file")
    (options, args) = parser.parse_args()

    fpm8210(query=options.com, filename=options.filename, FORCE=options.force)
