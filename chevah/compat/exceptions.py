# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Exceptions used in chevah.compat package.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from six import text_type


class CompatException(Exception):
    """
    Base compat repo exception.
    """
    def __init__(self, message=''):
        self.message = message

    def __repr__(self):
        result = u'CompatException %s' % (self.message)
        return result.encode('utf-8')


class ChangeUserException(CompatException):
    """
    User could not be impersonated.
    """


class AdjustPrivilegeException(CompatException):
    """
    Could not adjust process privileges.
    """


class CompatError(Exception):
    """
    Error raised by chevah.compat package.
    """

    def __init__(self, event_id, message):
        self.event_id = event_id
        self.message = message

    def __repr__(self):
        result = u'CompatError %s - %s' % (
            text_type(self.event_id), self.message)
        return result.encode('utf-8')

    def __str__(self):
        return self.__repr__()
