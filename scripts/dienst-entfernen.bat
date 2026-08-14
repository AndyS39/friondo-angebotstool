@echo off
rem Friondo Angebotstool: Autostart-Dienst wieder entfernen (als Administrator).
schtasks /End /TN "Friondo Angebotstool" >nul 2>&1
schtasks /Delete /F /TN "Friondo Angebotstool"
netsh advfirewall firewall delete rule name="Friondo Angebotstool"
echo Aufgabe und Firewall-Regel entfernt. Projektordner und Daten bleiben erhalten.
