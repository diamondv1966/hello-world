@echo off
rem Import what the scout bot collected, then build today's packet for approval.
chcp 65001 >nul
cd /d "%~dp0"
python aff.py import
python aff.py daily
python aff.py todo
