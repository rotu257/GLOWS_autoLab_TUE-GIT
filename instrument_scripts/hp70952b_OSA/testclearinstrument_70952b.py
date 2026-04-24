#! /home/user_rotu/GLOWS_autoLab_python3_venv/bin/python
import pyvisa

def clear_errors(inst):
    """
    Clear all non-hardware errors from the display’s queue.
    ES invokes the Report Errors utility, EG fetches the text.
    """
    inst.write('ES')                # ES = ERROR SCREEN (clears errors) :contentReference[oaicite:0]{index=0}&#8203;:contentReference[oaicite:1]{index=1}
    errs = inst.query('EG')         # EG = OUTPUT ERROR MESSAGE :contentReference[oaicite:2]{index=2}&#8203;:contentReference[oaicite:3]{index=3}
    return errs.strip()

def reset_display(inst):
    """
    Return the display graphics to the initial power-on state.
    IN = INITIALIZE (graphics) :contentReference[oaicite:4]{index=4}&#8203;:contentReference[oaicite:5]{index=5}
    """
    inst.write('IN')

def test_and_restore(gpib_addr='GPIB0::23::INSTR'):
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(gpib_addr)
    # Ensure proper line endings and a generous timeout
    inst.write_termination = '\r\n'
    inst.read_termination  = '\n'
    inst.timeout = 10000  # 10 s

    try:
        # 1) Identify
        idn = inst.query('ID')  # ID = OUTPUT IDENTIFICATION :contentReference[oaicite:6]{index=6}&#8203;:contentReference[oaicite:7]{index=7}
        print(f"Device ID: {idn.strip()}")

        # 2) Self-test
        inst.write('TE')            # TE = SELF TEST :contentReference[oaicite:8]{index=8}&#8203;:contentReference[oaicite:9]{index=9}
        result = inst.query('EG')   # EG = OUTPUT ERROR MESSAGE
        if result.strip():
            print("Self-test reported errors:\n", result.strip())
        else:
            print("Self-test passed with no errors.")

        # 3) Clear any lingering errors
        cleared = clear_errors(inst)
        if cleared:
            print("Cleared errors:\n", cleared)
        else:
            print("No errors to clear.")

        # 4) Reset to initial state
        reset_display(inst)
        print("Display reset to initial power-on state.")

    except pyvisa.VisaIOError as e:
        print("Communication error:", e)
    finally:
        inst.close()
        rm.close()

if __name__ == "__main__":
    test_and_restore()
