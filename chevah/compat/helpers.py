# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Any methods from here is a sign of bad design.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


def _(string):
    '''Placeholder for future gettext integration.'''
    return string


class NoOpContext(object):
    """
    A context manager that does nothing.
    """

    def __enter__(self):
        '''Do nothing.'''
        return self

    def __exit__(self, exc_type, exc_value, tb):
        '''Just propagate errors.'''
        return False


def force_unicode(value):
    """
    Convert the `value` to unicode.

    In case there are encoding errors when converting the invalid characters
    are replaced.
    """
    if value is None:
        return unicode(value)

    elif isinstance(value, unicode):
        return value

    def str_or_repr(value):
        try:
            return unicode(value)
        except Exception:
            # No unicode representation.
            # Try to decode the str()
            try:
                return unicode(str(value), encoding='utf-8', errors='replace')
            except Exception:
                # No luck with str, try repr()
                return unicode(repr(value), encoding='utf-8', errors='replace')

    result = str_or_repr(value)

    if isinstance(value, Exception) and result == '':
        # This is an exception without text representation.
        # Use the repr so that we get something.
        return unicode(repr(value), encoding='utf-8', errors='replace')

    return result
