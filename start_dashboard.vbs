Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd.exe /c python src\desktop_app.py > app_crash.log 2>&1", 0
Set WshShell = Nothing
