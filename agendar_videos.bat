@echo off
cd /d "%~dp0"
echo Agendando os kits de video para 11h e 19h todo dia...
schtasks /Create /F /TN "Levylly Videos 11h" /TR "\"%~dp0rodar_videos.bat\" auto" /SC DAILY /ST 11:00
schtasks /Create /F /TN "Levylly Videos 19h" /TR "\"%~dp0rodar_videos.bat\" auto" /SC DAILY /ST 19:00
echo Ligando o editor sozinho quando o Windows iniciar...
schtasks /Create /F /TN "Levylly Editor" /TR "\"%~dp0iniciar_editor.bat\"" /SC ONLOGON
echo.
echo Pronto! O PC precisa estar ligado nesses horarios.
echo Para cancelar: Agendador de Tarefas do Windows ^> apague as tarefas "Levylly ...".
pause
