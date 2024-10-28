# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Exceptions used in chevah_compat package.
"""


class CompatException(Exception):
    """
    Base compat repo exception.
    """

    def __init__(self, message=''):
        self.message = message

    def __repr__(self):
        return f'CompatException {self.message}'


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
    Error raised by chevah_compat package.
    """

    def __init__(self, event_id, message):
        self.event_id = event_id
        self.message = message

    def __repr__(self):
        return f'CompatError {self.event_id!s} - {self.message}'

    def __str__(self):
        return self.__repr__()
