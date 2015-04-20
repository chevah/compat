:: Batch command to test passing of Unicode arguments
:: and arguments with spaces from a Windows batch file
:: Make sure you call build command before this so that build folder is
:: updated.

@ECHO OFF

SET python_exe=lib\python.exe
if not exist %python_exe% (
    ECHO This must be called from the root build folder.
    PAUSE
    GOTO:EOF
)

ECHO -
ECHO ----- As file with -----
ECHO -
%python_exe% ..\chevah\compat\tests\manual\print_argv.py ^%*

echo -
ECHO ----- As module -----
ECHO -
%python_exe% -m chevah.compat.tests.manual.print_argv ^%*
