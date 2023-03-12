# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Shared code by all users compatibility layer.

Check chevah/server/static/events/events.json to make sure each CompatError
has unique ID.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import, unicode_literals
from chevah_compat.exceptions import CompatError


class CompatUsers(object):
    """
    Base class for users compatibility.
    """

    def raiseFailedToGetPrimaryGroup(self, username):
        """
        Helper for raising the exception from a single place.
        """
        message = 'Failed to get primary group for user "%s"' % username
        raise CompatError(1015, message)

    def raiseFailedToGetHomeFolder(self, username, text):
        """
        Helper for raising the exception from a single place.
        """
        values = (username, text)
        message = 'Could not get home folder for user "%s". %s' % values
        raise CompatError(1014, message)

    def raiseFailedtoCheckUserExists(self, username, text):
        """
        Helper for raising the exception with a specific ID.
        """
        message = u'Failed to check that user "%s" exists. %s' % (
            username, text)
        raise CompatError(1018, message)
