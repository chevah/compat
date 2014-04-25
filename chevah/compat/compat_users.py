# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Shared code by all users compatibility layer.
"""
from chevah.compat.exceptions import CompatError


class CompatUsers(object):
    """
    Base class for users compatibility.
    """

    def raiseFailedToGetPrimaryGroup(self, username):
        """
        Helper for raising the exception from a single place.
        """
        message = u'Failed to get primary group for user "%s"' % username
        raise CompatError(1015, message.encode('utf-8'))

    def raiseFailedToGetHomeFolder(self, username, text):
        """
        Helper for raising the exception from a single place.
        """
        values = (username, text)
        message = u'Could not get home folder for user "%s". %s' % values
        raise CompatError(1014, message.encode('utf-8'))
