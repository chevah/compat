# Copyright (c) 2010-2012 Adi Roiban.
# See LICENSE for details.
'''Provides informatin about capabilites for a process on Unix.'''
from __future__ import with_statement

from zope.interface import implements

from chevah.compat.capabilities import BaseProcessCapabilities
from chevah.compat.exceptions import ChangeUserException
from chevah.compat.helpers import (
    _,
    )
from chevah.compat.interfaces import IProcessCapabilities
from chevah.compat.unix_users import _ExecuteAsUser


class UnixProcessCapabilities(BaseProcessCapabilities):
    '''Container for Unix capabilities detection.'''

    implements(IProcessCapabilities)

    @property
    def impersonate_local_account(self):
        '''See `IProcessCapabilities`.

        On Unix systems, this means that we can run as root account.
        '''
        try:
            with _ExecuteAsUser(euid=0, egid=0):
                return True
        except ChangeUserException:
            return False

    @property
    def create_home_folder(self):
        '''See `IProcessCapabilities`.'''
        return self.impersonate_local_account

    @property
    def get_home_folder(self):
        """
        See `IProcessCapabilities`.

        On Unix we can get home folder since /etc/passwd is world readable.

        This code is not 100% valid.
        When PAM / LDAP or other external identity managers are used, there
        may be a case where we can not retrieve the home folder.

        This is a corner case and we will deal with it first time a
        customer will have this problem.
        """
        return True

    def getCurrentPrivilegesDescription(self):
        '''Return a text describing current priviledges.

        On Unix it informs if the process has root capabilities.
        '''
        if self.impersonate_local_account:
            return _(u'root capabilities enabled.')
        else:
            return _(u'root capabilities disabled.')
