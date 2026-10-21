@echo off
cd /d %~dp0
title Editor de videos - LEVYLLY
echo Editor ligado. Deixe esta janela aberta.
venv\Scripts\python editor_bot.py
pause
