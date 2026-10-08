@echo off
:: Navigate to the JarvisBrain root directory so plugins and relative paths work
cd /d "C:\Users\Abrorjon\Documents\Projects\Personal Assistant\JarvisBrain"

:: Start the Universal Worker in the background
start "" pythonw src\agent_daemon.py

:: Start the Telegram Responder in the background
start "" pythonw src\relay.py
