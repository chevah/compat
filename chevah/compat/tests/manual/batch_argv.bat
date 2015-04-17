:: Batch command to test passing of Unicode arguments
:: and arguments with spaces from a Windows batch file

@ECHO OFF
CHCP 65001 > nul
SET PYTHONIOENCODING=utf-8

SET python_exe=lib\python.exe
if not exist %python_exe% (
    ECHO This must be called from the root build folder.
    PAUSE
    GOTO:EOF
)

%python_exe% -m chevah.compat.tests.manual.print_argv ^%*^
