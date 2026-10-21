@echo off
cd /d "%~dp0"
for /f "delims=" %%f in ('dir /b /o-d videos\*.mp4 2^>nul') do (set "VIDEO=videos\%%f" & goto achou)
echo Nenhum video na pasta videos. Rode o robo primeiro.
pause
exit /b
:achou
echo Enviando %VIDEO% para os rascunhos do TikTok...
venv\Scripts\python tiktok.py enviar "%VIDEO%"
