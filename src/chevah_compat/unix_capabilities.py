# Copyright (c) 2010-2012 Adi Roiban.
# See LICENSE for details.
"""
Provides information about capabilities for a process on Unix.
"""
import platform

from zope.interface import implementer

from chevah_compat.capabilities import BaseProcessCapabilities
from chevah_compat.exceptions import ChangeUserException
from chevah_compat.helpers import _
from chevah_compat.interfaces import IProcessCapabilities
from chevah_compat.unix_users import _ExecuteAsUser


@implementer(IProcessCapabilities)
class UnixProcessCapabilities(BaseProcessCapabilities):
    '''Container for Unix capabilities detection.'''


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
        """
        Return a text describing current privileges.

        On Unix it informs if the process has root capabilities.
        """
        if self.impersonate_local_account:
            return _(u'root capabilities enabled.')
        else:
            return _(u'root capabilities disabled.')

    @property
    def symbolic_link(self):
        """
        See `IProcessCapabilities`.
        """
        return True

    @property
    def pam(self):
        """
        See `IProcessCapabilities`.
        """
        if self.os_name == 'openbsd':
            return False

        if self.os_name == 'hpux':
            # We don't support PAM on HPUX.
            return False

        if self.os_name == 'linux':
            import distro
            distro_name = distro.id()
            if distro_name == 'alpine':
                return False

        return True
