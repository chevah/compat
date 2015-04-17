"""
Call this script either as a file or as a module to see that arguments are
in Unicode.

Like::

    python -m chevah.compat.tests.manual.print_argv ARG1 ARG2
    python chevah/compat/tests/manual/print_argv.py ARG1 ARG2
"""
import sys
from chevah import compat

print sys.argv
