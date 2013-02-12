# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Exceptions used in chevah.compat package.
"""


class CompatException(Exception):
    """
    Base compat repo exception.
    """


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
        return 'CompatError %s - %s' % (
            str(self.event_id), self.message.encode('utf-8'))

    def __str__(self):
        return self.__repr__()
