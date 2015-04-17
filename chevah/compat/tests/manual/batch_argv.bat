:: Batch command to test passing of Unicode arguments
:: and arguments with spaces from a Windows batch file

@ECHO OFF
CHCP 65001 > nul
SET PYTHONIOENCODING=utf-8

CD %~dp0
if not exist lib\python.exe (
    ECHO This file must be called from the root build folder.
    PAUSE
    GOTO:EOF
)

lib\python.exe -m chevah.compat.tests.manual.print_argv ^%*^
