#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
import pyvisa

def test_instrument(gpib_address='GPIB0::23::INSTR'):
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(gpib_address)
    # Ensure the right terminations and enough timeout
    inst.write_termination = '\r\n'
    inst.read_termination  = '\n'
    inst.timeout = 30000

    # Query ID (must be 'ID', not '*IDN?')
    idn = inst.query('ID')
    print("Device ID:", idn.strip())

    # Run built-in self-test
    inst.write('TE')          # SELF TEST
    errors = inst.query('EG') # OUTPUT ERROR MESSAGE
    if errors.strip():
        print("Self-test errors:\n", errors)
    else:
        print("Self-test passed with no errors.")
    inst.close()
    rm.close()

if __name__ == "__main__":
    test_instrument()