# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Shared code by all users compatibility layer.

Check chevah/server/static/events/events.json to make sure each CompatError
has unique ID.
"""

from chevah_compat.exceptions import CompatError


class CompatUsers:
    """
    Base class for users compatibility.
    """

    def raiseFailedToGetPrimaryGroup(self, username):
        """
        Helper for raising the exception from a single place.
        """
        message = f'Failed to get primary group for user "{username}"'
        raise CompatError(1015, message)

    def raiseFailedToGetHomeFolder(self, username, text):
        """
        Helper for raising the exception from a single place.
        """
        values = (username, text)
        message = 'Could not get home folder for user "{}". {}'.format(*values)
        raise CompatError(1014, message)

    def raiseFailedtoCheckUserExists(self, username, text):
        """
        Helper for raising the exception with a specific ID.
        """
        message = f'Failed to check that user "{username}" exists. {text}'
        raise CompatError(1018, message)
