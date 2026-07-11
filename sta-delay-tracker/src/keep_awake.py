"""Prevent the machine from idle-sleeping while collection runs.

The poller only logs while the OS is awake; this laptop slept for ~3.5 days
(Jul 7-10) and lost data. Sleep/hibernate settings are managed and the lid
policy is hidden on this loaner, so we can't change them. This does NOT need
admin: it calls the Win32 SetThreadExecutionState API to tell Windows the
system is "in use," which blocks idle sleep for as long as this process lives.
The display is still allowed to turn off (we only assert SYSTEM_REQUIRED).

Note: this cannot stop a manually-closed-lid sleep, only idle sleep.

Run detached, like the poller:  python src/keep_awake.py
"""
import ctypes
import time
from datetime import datetime

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def main():
    kernel32 = ctypes.windll.kernel32
    # assert once as continuous; re-assert periodically as a belt-and-suspenders
    while True:
        rc = kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        if rc == 0:
            print(f"[{datetime.now()}] SetThreadExecutionState failed")
        time.sleep(60)


if __name__ == "__main__":
    main()
