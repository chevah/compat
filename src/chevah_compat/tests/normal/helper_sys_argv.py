"""
Helper script called to check sys.argv values.
"""

from __future__ import absolute_import, division, print_function

import sys

# We print all after the first argument as the first argument should be
# ignored.
# First list arguments before importing compat.
sys.stdout.write(repr(sys.argv[1:]))

# List after importing.
import chevah_compat  # noqa:E402

# Silence the linter.
chevah_compat
sys.stdout.write(repr(sys.argv[1:]))
