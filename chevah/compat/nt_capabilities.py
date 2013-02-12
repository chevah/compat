# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Provides information about capabilities for a process on Windows.
"""
from __future__ import with_statement

from contextlib import contextmanager
import platform
import win32api
import win32process
import win32security

from zope.interface import implements

from chevah.compat.exceptions import AdjustPrivilegeException
from chevah.compat.interfaces import IProcessCapabilities


class NTProcessCapabilities(object):
    '''Container for NT capabilities detection.'''

    implements(IProcessCapabilities)

    def getCurrentPrivilegesDescription(self):
        """
        Return a text describing current privileges.
        """
        result = []

        with self._openProcess(win32security.TOKEN_QUERY) as process_token:
            privileges = win32security.GetTokenInformation(
                process_token, win32security.TokenPrivileges)

            for privilege in privileges:
                name = win32security.LookupPrivilegeName('', privilege[0])
                value = unicode(privilege[1])
                result.append(name + u':' + value)

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

    @contextmanager
    def _openProcess(self, mode=win32security.TOKEN_ALL_ACCESS):
        """
        Context manager for opening current process token with specified
        access mode.

        By default it uses all access mode.

        Valid access modes:
        http://msdn.microsoft.com/en-us/library/windows/desktop/aa374905.aspx
        """
        process_token = None
        try:
            process_token = win32security.OpenProcessToken(
                win32process.GetCurrentProcess(),
                mode)
            yield process_token
        finally:
            if process_token:
                win32api.CloseHandle(process_token)

    def _adjustPrivilege(self, privilege_name, enable=False):
        """
        Adjust (enable/disable) privileges for the current process.

        List of valid privilege names:
        http://msdn.microsoft.com/en-us/library/windows/desktop/bb530716.aspx

        Raises AdjustPrivilegeException if adjusting fails.
        """
        with self._openProcess() as process_token:
            try:
                if enable:
                    new_state = win32security.SE_PRIVILEGE_ENABLED
                else:
                    new_state = 0

                new_privileges = (
                    (win32security.LookupPrivilegeValue('', privilege_name),
                     new_state),
                )

                win32security.AdjustTokenPrivileges(process_token, 0,
                    new_privileges)
            except win32security.error, error:
                raise AdjustPrivilegeException(error)

    def _hasPrivilege(self, privilege_name):
        """
        Check if the current process has the specified privilege name.

        Returns False otherwise.
        """
        with self._openProcess(win32security.TOKEN_QUERY) as process_token:
            privilege_value = win32security.LookupPrivilegeValue('',
                privilege_name)

            privileges = win32security.GetTokenInformation(
                process_token, win32security.TokenPrivileges)

            for privilege in privileges:
                value = privilege[0]
                state = privilege[1]
                # bitwise flag
                # 0 - not set
                # 1 - win32security.SE_PRIVILEGE_ENABLED_BY_DEFAULT
                # 2 - win32security.SE_PRIVILEGE_ENABLED
                # 4 - win32security.SE_PRIVILEGE_REMOVED
                # -2147483648 - win32security.SE_PRIVILEGE_USED_FOR_ACCESS

                if privilege_value == value:
                    enabled = (
                        state & win32security.SE_PRIVILEGE_ENABLED ==
                        win32security.SE_PRIVILEGE_ENABLED)
                    enabled_by_default = (
                        state & win32security.SE_PRIVILEGE_ENABLED_BY_DEFAULT
                        == win32security.SE_PRIVILEGE_ENABLED_BY_DEFAULT)

                    if enabled or enabled_by_default:
                        return True
                    else:
                        return False

        return False

    @contextmanager
    def _elevatePrivileges(self, *privileges):
        """
        Elevate current process privileges to include the specified ones.

        Raises AdjustPrivilegeException if elevating the privileges fails.
        """
        try:
            for privilege in privileges:
                self._adjustPrivilege(privilege, True)
            yield
        finally:
            for privilege in privileges:
                self._adjustPrivilege(privilege, False)
