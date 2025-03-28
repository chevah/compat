# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Provides information about capabilities for a process on Windows.
"""

import platform
from contextlib import contextmanager

import pywintypes
import win32api
import win32process
import win32security
from zope.interface import implementer

from chevah_compat.capabilities import BaseProcessCapabilities
from chevah_compat.exceptions import AdjustPrivilegeException
from chevah_compat.interfaces import IProcessCapabilities


@implementer(IProcessCapabilities)
class NTProcessCapabilities(BaseProcessCapabilities):
    """Container for NT capabilities detection."""

    def getCurrentPrivilegesDescription(self):
        """
        Return a text describing current privileges.
        """
        result = []

        for privilege in self._getAvailablePrivileges():
            name = win32security.LookupPrivilegeName('', privilege[0])
            value = str(privilege[1])
            result.append(name + ':' + value)

        return ', '.join(result)

    def _getAvailablePrivileges(self):
        """
        Return a list with tuples for privileges attached to process.

        Each list item is in the format:
        (PRIVILEGE_ID, PRIVILEGE_STATE)
        """
        with self._openProcess(win32security.TOKEN_QUERY) as process_token:
            return win32security.GetTokenInformation(
                process_token,
                win32security.TokenPrivileges,
            )

    @property
    def impersonate_local_account(self):
        """
        See `IProcessCapabilities`.
        """
        privileges = self.getCurrentPrivilegesDescription()
        if 'SeImpersonatePrivilege' in privileges:
            return True

        return False

    @property
    def pam(self):
        """
        See `IProcessCapabilities`.
        """
        # On Windows we don't support PAM.
        return False

    @property
    def create_home_folder(self):
        """
        See `IProcessCapabilities`.
        """
        privileges = self.getCurrentPrivilegesDescription()
        if (
            'SeBackupPrivilege' in privileges
            and 'SeRestorePrivilege' in privileges
        ):
            return True
        return False

    @property
    def get_home_folder(self):
        """
        See `IProcessCapabilities`.

        This is just hardcoded to the Windows version.
        See https://trac.chevah.com/ticket/920 for more details.
        """
        try:
            version = platform.version()
            if not version:
                return False
            major_version = int(version.split('.')[0])
        except Exception:
            return False

        if not major_version:
            return False
        if major_version < 6:
            return False
        return True

    @contextmanager
    def _openProcess(self, mode):
        """
        Context manager for opening current thread token with specified
        access mode.

        It will revert to process token if unable to open current thread
        token.

        Valid access modes:
        http://msdn.microsoft.com/en-us/library/windows/desktop/aa374905.aspx
        """
        process_token = None
        try:
            # Although there is always a current thread, Windows will not
            # allow opening it's token before impersonation and/or the
            # creation of other thread(s). Thus, we are reverting to the
            # process token in case of failure.
            #
            # Alas always opening the process token will not work when we
            # use impersonation. Firstly, the opening will fail; secondly, the
            # impersonation will affect only the current thread and not the
            # entire process.
            try:
                # See Trac ticket 2095.
                # Implement distinct API for opening currently impersonated
                # user token.
                process_token = win32security.OpenThreadToken(
                    win32api.GetCurrentThread(),
                    mode,
                    0,
                )
            except Exception:
                process_token = win32security.OpenProcessToken(
                    win32process.GetCurrentProcess(),
                    mode,
                )

            yield process_token
        finally:
            if process_token:
                win32api.CloseHandle(process_token)

    @contextmanager
    def _elevatePrivileges(self, *privileges):
        """
        Elevate current process privileges to include the specified ones.

        If the privileges are already enabled nothing is changed.

        Raises AdjustPrivilegeException if elevating the privileges fails.
        """

        missing_privileges = []
        try:
            for privilege_name in privileges:
                state = self._getPrivilegeState(privilege_name)
                if not self._isPrivilegeStateAvailable(state):
                    message = (
                        f'Process does not have {privilege_name} privilege.'
                    )
                    raise AdjustPrivilegeException(message.encode('utf-8'))

                if not self._isPrivilegeStateEnabled(state):
                    missing_privileges.append(privilege_name)

            for privilege_name in missing_privileges:
                self._adjustPrivilege(privilege_name, True)
            yield
        finally:
            for privilege_name in missing_privileges:
                self._adjustPrivilege(privilege_name, False)

    def _adjustPrivilege(self, privilege_name, enable=False):
        """
        Adjust (enable/disable) privileges for the current process.

        List of valid privilege names:
        http://msdn.microsoft.com/en-us/library/windows/desktop/bb530716.aspx

        Raises AdjustPrivilegeException if adjusting fails.
        """
        if enable:
            new_state = win32security.SE_PRIVILEGE_ENABLED
        else:
            new_state = 0

        # Privileges are passes as a list of tuples.
        # We only update one privilege at a time.
        new_privileges = [
            (win32security.LookupPrivilegeValue('', privilege_name), new_state),
        ]
        process_mode = win32security.TOKEN_ALL_ACCESS
        with self._openProcess(mode=process_mode) as process_token:
            try:
                win32security.AdjustTokenPrivileges(
                    process_token,
                    0,
                    new_privileges,
                )
            except win32security.error as error:
                raise AdjustPrivilegeException(str(error))

    def _getPrivilegeID(self, privilege_name):
        """
        Return numeric ID for `privilege_name`.

        This is here since it is also used as helper in tests.

        Available names are at:
        http://msdn.microsoft.com/en-us/library/windows/
            desktop/bb530716(v=vs.85).aspx
        """
        return win32security.LookupPrivilegeValue('', privilege_name)

    def _getPrivilegeState(self, privilege_name):
        """
        Return state for `privilege_name`.

        Status can be:
        * 'present'
        * 'enabled'
        * 'enabled-by-default'
        * 'removed'
        * 'absent'

        Try to avoid using this method and defer to _hasPrivilege* methods.

        In Windows, state is a mask so a state can be both enabled and
        enabled-by-default and removed. This tries to implement a priority,
        so a privilege which was removed will only return removed.
        """
        result = 'absent'

        try:
            target_id = self._getPrivilegeID(privilege_name)
        except pywintypes.error:
            # We fail to query privilege so it does not exists.
            return result

        for privilege in self._getAvailablePrivileges():
            privilege_id = privilege[0]
            state = privilege[1]
            # bitwise flag
            # 0 - not set
            # 1 - win32security.SE_PRIVILEGE_ENABLED_BY_DEFAULT
            # 2 - win32security.SE_PRIVILEGE_ENABLED
            # 4 - win32security.SE_PRIVILEGE_REMOVED
            # -2147483648 - win32security.SE_PRIVILEGE_USED_FOR_ACCESS

            if privilege_id != target_id:
                continue

            if (
                state & win32security.SE_PRIVILEGE_REMOVED
            ) == win32security.SE_PRIVILEGE_REMOVED:
                return 'removed'

            if (
                state & win32security.SE_PRIVILEGE_ENABLED_BY_DEFAULT
            ) == win32security.SE_PRIVILEGE_ENABLED_BY_DEFAULT:
                return 'enabled-by-default'

            if (
                state & win32security.SE_PRIVILEGE_ENABLED
            ) == win32security.SE_PRIVILEGE_ENABLED:
                return 'enabled'

            # Set state as present and stop looking for other names.
            result = 'present'
            break

        return result

    def _isPrivilegeEnabled(self, privilege_name):
        """
        Return True if the process has the specified `privilege_name`
        enabled.
        """
        state = self._getPrivilegeState(privilege_name)
        return self._isPrivilegeStateEnabled(state)

    def _isPrivilegeStateEnabled(self, state):
        """
        Retrun True if state is one of the enabled values.
        """
        if state in ['enabled', 'enabled-by-default']:
            return True
        return False

    def _isPrivilegeStateAvailable(self, state):
        """
        Return True if state is one of the values in which it is available
        to the process.
        """
        if state in ['present', 'enabled', 'enabled-by-default']:
            return True
        return False

    def _hasPrivilege(self, privilege_name):
        """
        Return True if `privilege` name is available and is enabled
        or can be enabled.
        """
        state = self._getPrivilegeState(privilege_name)
        return self._isPrivilegeStateAvailable(state)

    @property
    def symbolic_link(self):
        """
        See `IProcessCapabilities`.

        Enabled with SE_CREATE_SYMBOLIC_LINK_NAME.

        Supported on Vista and above.
        """
        if self._hasPrivilege(win32security.SE_CREATE_SYMBOLIC_LINK_NAME):
            return True
        return False
