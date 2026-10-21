@echo off
cd /d "%~dp0"
echo Buscando produto e mandando o kit (storyboard + prompts) no Telegram...
venv\Scripts\python bot_videos.py --modo ia
echo.
echo Pronto! Olhe o seu Telegram. Se nao chegou, mande um print desta janela.
if "%1"=="" pause
