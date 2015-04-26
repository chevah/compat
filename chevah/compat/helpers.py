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
