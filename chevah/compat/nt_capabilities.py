# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Provides information about capabilities for a process on Windows.
"""
from __future__ import with_statement
import platform
import win32api
import win32process
import win32security

from zope.interface import implements

from chevah.compat.interfaces import IProcessCapabilities


class NTProcessCapabilities(object):
    '''Container for NT capabilities detection.'''

    implements(IProcessCapabilities)

    def getCurrentPrivilegesDescription(self):
        '''Return a text describing current privileges.'''
        result = []
        process_token = win32security.OpenProcessToken(
            win32process.GetCurrentProcess(),
            win32security.TOKEN_QUERY,
            )

        privileges = win32security.GetTokenInformation(
            process_token, win32security.TokenPrivileges)

        for privilege in privileges:
            name = win32security.LookupPrivilegeName('', privilege[0])
            value = unicode(privilege[1])
            result.append(name + u':' + value)
        win32api.CloseHandle(process_token)
        return u', '.join(result)

    @property
    def impersonate_local_account(self):
        """
        See `IProcessCapabilities`.

        On Windows we can always impersonate local accounts.
        """
        return True

    @property
    def create_home_folder(self):
        """
        See `IProcessCapabilities`.
        """
        privileges = self.getCurrentPrivilegesDescription()
        if ('SeBackupPrivilege' in privileges and
                'SeRestorePrivilege' in privileges):
            return True
        else:
            return False

    @property
    def get_home_folder(self):
        """
        See `IProcessCapabilities`.

        Right now only Windows 2008 and 7 are supported.

        # FIXME:920:
        """
        try:
            version = platform.version()
            if not version:
                return False
            major_version = int(version.split('.')[0])
            if not major_version:
                return False
            if major_version < 6:
                return False
            return True
        except:
            return False

    def _adjustPrivilege(self, privilege_name, enable=False):
        """
        privilege_name ex: win32security.SE_BACKUP_NAME
        remove - win32security.SE_PRIVILEGE_REMOVED
        enable - win32security.SE_PRIVILEGE_ENABLED
        disable - 0
        """
        process_token = win32security.OpenProcessToken(
            win32process.GetCurrentProcess(),
            win32security.TOKEN_ALL_ACCESS)

        if enable:
            new_state = win32security.SE_PRIVILEGE_ENABLED
        else:
            new_state = 0

        new_privileges = (
            (win32security.LookupPrivilegeValue('', privilege_name),
             new_state),
        )

        win32security.AdjustTokenPrivileges(process_token, 0, new_privileges)
        win32api.CloseHandle(process_token)
