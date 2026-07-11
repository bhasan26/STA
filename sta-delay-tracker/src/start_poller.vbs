' Launches the STA delay tracker poller hidden (no console window) at user logon.
' Placed in the Startup folder as a reboot-resilience mechanism, since Task
' Scheduler registration is blocked by policy on this machine.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\Users\Student\STA\sta-delay-tracker"
shell.Run "cmd /c python src\poller.py >> logs\poller.log 2>> logs\poller_err.log", 0, False
