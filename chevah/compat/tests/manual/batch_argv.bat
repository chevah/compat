:: Batch command to test passing of Unicode arguments
:: and arguments with spaces from a Windows batch file
:: Make sure you call build command before this so that build folder is
:: updated.

@ECHO OFF
CHCP 65001 > nul
SET PYTHONIOENCODING=utf-8

SET python_exe=lib\python.exe
if not exist %python_exe% (
    ECHO This must be called from the root build folder.
    PAUSE
    GOTO:EOF
)

ECHO "Call as file"
%python_exe% ..\chevah\compat\tests\manual\print_argv.py ^%*^

ECHO "Call as module"
%python_exe% -m chevah.compat.tests.manual.print_argv ^%*^
