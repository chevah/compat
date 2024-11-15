# ruff: noqa: T201
"""
Call this script either as a file or as a module to see that arguments are
in Unicode.

Like::

    python -m chevah_compat.tests.manual.print_argv ARG1 ARG2
    python chevah/compat/tests/manual/print_argv.py ARG1 ARG2

Make sure you call build command before calling this so that build folder
is updated.
"""

import os
import sys

print('Before import (for module import is already called)')
print(sys.argv)

from chevah import compat  # noqa:E402

# Silence the linter
compat
print('After import')
print(sys.argv)

if os.name == 'nt':
    from chevah_compat.nt_unicode_argv import get_unicode_argv

    print('Call again')
    print(get_unicode_argv())
