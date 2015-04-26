"""
Helper script called to check sys.argv values.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import sys

# We print all after the first argument as the first argument should be
# ignored.
# First list arguments before importing compat.
sys.stdout.write(repr(sys.argv[1:]))

# List after importing.
from chevah import compat  # noqa
# Silence the linter.
compat
sys.stdout.write(repr(sys.argv[1:]))
