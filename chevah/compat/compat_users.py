# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Shared code by all users compatibility layer.
"""
from chevah.compat.exceptions import CompatError
from chevah.compat.helpers import _


class CompatUsers(object):
    """
    Base class for users compatibility.
    """

    def raiseFailedToGetPrimaryGroup(self, username):
        """
        Helper for raising the exception from a single place.
        """
        raise CompatError(1015, _(
            u'Failed to get primary group for user "%s"' % (username)))

    def raiseFailedToGetHomeFolder(self, username, text):
        """
        Helper for raising the exception from a single place.
        """
        raise CompatError(
            1014,
            _(u'Could not get home folder for user "%s". %s' % (
                username, text)))
