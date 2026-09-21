@echo off
setlocal

cd /d "%~dp0..\frontend"
npm.cmd run dev -- --host localhost --port 5173

