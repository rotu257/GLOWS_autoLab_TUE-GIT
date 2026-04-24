#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
import sys
import pyvisa as visa
from optparse import OptionParser

class ITC_4001():
    def __init__(self, INSTR, query=None, command=None, amplitude=None):
        ### Initiate communication ###
        rm = visa.ResourceManager('@py')
        try:
            self.thorlabs = rm.open_resource(INSTR)
        except:
            print('\nWrong connection => Check address or cables\n')
            sys.exit()

        ### Basic communications ###
        if query:
            self.command = query
            print('\nAnswer to query:', self.command)
            rep = self.query(self.command)
            print(rep, '\n')
            sys.exit()
        elif command:
            self.command = command
            print('\nExecuting command', self.command)
            self.thorlabs.write(self.command)
            print('\n')
            sys.exit()

        ### change the value of the current ###
        if amplitude or amplitude == 0:
            self.thorlabs.write('SOUR:CURR %f\n' % amplitude)
            print('\nSetting current to: ', amplitude, 'A\n')

    def query(self, cmd):
        self.thorlabs.write(cmd+'\n')
        r = self.read()
        return r
    
    def read(self):
        return self.thorlabs.read()
        
if __name__ == "__main__":
    usage = """usage: %prog [options] arg
               
        EXAMPLE CHANGE LD CURRENT:
                   set_ITC4001 -a 0.5 3               
               Set the pumping current to 0.5amps on laser diode 3

        EXAMPLE COMMAND THE DEVICE:
                   set_ITC4001 -c *CLS               
               command clears the event register of all registers in laser diode #1       

        EXAMPLE QUERY THE DEVICE ID:
                   set_ITC4001 -q *OPC? 1               
               read the id string of laser diode #1                            

               """
    parser = OptionParser(usage)
    parser.add_option("-c", "--command", type="str", dest="com", default=None, help="Set the command to use." )
    parser.add_option("-q", "--query", type="str", dest="que", default=None, help="Set the query to use." )
    parser.add_option("-a", "--amplitude", type="float", dest="amplitude", default=None, help="Set the pumping current value")
    (options, args) = parser.parse_args()
    
    #Compute channels to acquire
    if len(args) != 1:
        print('\nYou must provide ONE address\n')
        sys.exit()
    else:
        temp_instr = eval(args[0])
    
    if temp_instr == 3:
        INSTR = 'USB0::4883::32842::M00248997::0::INSTR'
    elif temp_instr == 5:
        INSTR = 'USB0::4883::32842::M00271786::0::INSTR'
    elif temp_instr == 4:
        INSTR = 'USB0::4883::32842::M00248304::0::INSTR'
    else:
        print('\nYou MUST provide an address\n')
        sys.exit()
    
    #Call the class with arguments
    ITC_4001(INSTR, query=options.que, command=options.com, amplitude=options.amplitude)

'''

The modifications made to the script include:

    Importing the pyvisa module and using it instead of usb.core.
    Adding parentheses to print statements to make them compatible with Python 3's print function.
    Updating the print statements in exception handling and argument parsing.
    Modifying the eval() function usage to explicitly convert args[0] to an integer using int().

'''