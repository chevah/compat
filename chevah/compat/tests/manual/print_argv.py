"""
Call this script either as a file or as a module to see that arguments are
in Unicode.

Like::

    python -m chevah.compat.tests.manual.print_argv ARG1 ARG2
    python chevah/compat/tests/manual/print_argv.py ARG1 ARG2
"""
import sys
print 'Before import (for module import is already called)'
print sys.argv

from chevah import compat
print 'After import'
print sys.argv

from chevah.compat.nt_unicode_argv import get_unicode_argv
print 'Call again'
print get_unicode_argv()
print 'And again'
print get_unicode_argv()
