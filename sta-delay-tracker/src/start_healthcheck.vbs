' Launches the STA poller health check in hourly-loop mode, hidden, at logon.
' Mirrors start_poller.vbs — Task Scheduler is blocked by policy on this machine,
' so the Startup folder is the reboot-resilience mechanism.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\Users\Student\STA\sta-delay-tracker"
shell.Run "cmd /c python src\health_check.py --loop >> logs\health_stdout.log 2>&1", 0, False
