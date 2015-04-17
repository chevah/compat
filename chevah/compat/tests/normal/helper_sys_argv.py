"""
Helper script called to check sys.argv values.
"""
import sys

# We print all after the first argument as the first argument should be
# ignored.
sys.stdout.write(repr(sys.argv[1:]))
