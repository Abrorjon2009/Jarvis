Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw src\desktop_app.py", 0
Set WshShell = Nothing
