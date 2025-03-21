# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Adapter for working with NT users.
"""

from ctypes import (
    POINTER,
    byref,
    c_uint,
    c_wchar_p,
    create_unicode_buffer,
    windll,
)

import pythoncom
import pywintypes
import win32net
import win32profile
import win32security
from win32com.shell import shell, shellcon
from zope.interface import implementer

from chevah_compat.compat_users import CompatUsers
from chevah_compat.constants import CSIDL_FLAG_CREATE, WINDOWS_PRIMARY_GROUP
from chevah_compat.exceptions import ChangeUserError
from chevah_compat.helpers import NoOpContext
from chevah_compat.interfaces import (
    IFileSystemAvatar,
    IHasImpersonatedAvatar,
    IOSUsers,
)

# We can not import chevah_compat.process_capabilities as it would
# create a circular import.
from chevah_compat.nt_capabilities import NTProcessCapabilities
from chevah_compat.winerrors import ERROR_NONE_MAPPED

advapi32 = windll.advapi32
GetUserNameW = advapi32.GetUserNameW
GetUserNameW.argtypes = [c_wchar_p, POINTER(c_uint)]
GetUserNameW.restype = c_uint

# This is initialized at this module level so that it can be reuse in the
# whole module as a normal import from chevah_compat.
process_capabilities = NTProcessCapabilities()


class MissingProfileFolderException(Exception):
    """
    Non existing user profile folder exception.
    """


@implementer(IOSUsers)
class NTUsers(CompatUsers):
    """
    Container for NT users specific methods.
    """

    def getCurrentUserName(self):
        """
        Return the name of the account under which the current
        process is executed.
        """
        return get_current_username()

    def getHomeFolder(self, username, token=None):
        """
        Get home folder for local user.
        """
        # TODO: Replace with decorator that will raise an exception when
        # 2119

        # insufficient capabilities.
        if not process_capabilities.get_home_folder:
            message = (
                'Operating system does not support getting home folder '
                f'for account "{username}".'
            )
            self.raiseFailedToGetHomeFolder(username, message)

        try:
            if token is None:
                if username != self.getCurrentUserName():
                    self.raiseFailedToGetHomeFolder(
                        username,
                        'Invalid username/token combination.',
                    )
                return self._getHomeFolderPath()
            return self._getHomeFolder(username, token)
        except MissingProfileFolderException:
            self.raiseFailedToGetHomeFolder(
                username,
                'Failed to get home folder path.',
            )

    def _getHomeFolder(self, username, token):
        """
        Return home folder for specified `username` and `token`.
        """

        def _safe_get_home_path():
            try:
                with self.executeAsUser(username, token):
                    return self._getHomeFolderPath(token)
            except ChangeUserError as error:
                self.raiseFailedToGetHomeFolder(username, error.message)

        try:
            return _safe_get_home_path()
        except MissingProfileFolderException:
            # We try to create the profile and then try one last
            # time to get the home folder.
            self._createLocalProfile(username, token)
            return _safe_get_home_path()

    def _getHomeFolderPath(self, token=None):
        """
        It `token` is `None` it will get current user's home folder path,
        otherwise it will return the home folder of the token's user.
        """
        # In windows, you can choose to care about local versus
        # roaming profiles.
        #
        # For example, to ask for the roaming 'Application Data' directory:
        #  (CSIDL_APPDATA asks for the roaming,
        #   CSIDL_LOCAL_APPDATA for the local one)
        #
        #  (See microsoft references for further CSIDL constants)
        #  http://msdn.microsoft.com/en-us/library/bb762181(VS.85).aspx
        try:
            # Force creation of user profile folder if not already
            # existing.
            path = shell.SHGetFolderPath(
                0,
                shellcon.CSIDL_PROFILE | CSIDL_FLAG_CREATE,
                token,
                0,
            )
        except pythoncom.com_error:
            raise MissingProfileFolderException

        return path

    def _createLocalProfile(self, username, token):
        """
        Create the local profile for specified `username`.
        """
        try:
            primary_domain_controller, name = self._parseUPN(username)

            user_info_4 = win32net.NetUserGetInfo(
                primary_domain_controller,
                name,
                4,
            )

            profile_path = user_info_4['profile']
            # LoadUserProfile doesn't like an empty string.
            if not profile_path:
                profile_path = None

            profile_info = {
                'UserName': name,
                'ServerName': primary_domain_controller,
                'Flags': 0,
                'ProfilePath': profile_path,
            }

            profile = win32profile.LoadUserProfile(token, profile_info)
            win32profile.UnloadUserProfile(token, profile)
        except (win32security.error, pywintypes.error) as error:
            (error_id, error_call, error_message) = error.args
            error_text = (
                'Failed to create user profile. '
                'Make sure you have SeBackupPrivilege and '
                'SeRestorePrivilege. (%d: %s - %s)'
                % (error_id, error_call, error_message)
            )
            self.raiseFailedToGetHomeFolder(username, error_text)

    def userExists(self, username):
        """
        Returns `True` if username exists on this system.
        """
        # Windows is stupid and return True for empty user.
        # Even when guest account is disabled.
        if not username:
            return False

        try:
            win32security.LookupAccountName('', username)
        except (win32security.error, pywintypes.error) as error:
            (number, name, message) = error.args
            if number == ERROR_NONE_MAPPED:
                return False
            error_text = f'[{number}] {name} {message}'
            self.raiseFailedtoCheckUserExists(username, error_text)

        return True

    def getGroupForUser(self, username, groups, token):
        """
        See: IOSUsers
        """
        if not groups:
            raise ValueError("Groups for validation can't be empty.")

        primary_domain_controller, name = self._parseUPN(username)

        for group in groups:
            try:
                group_sid, group_domain, group_type = (
                    win32security.LookupAccountName(
                        primary_domain_controller,
                        group,
                    )
                )
            except (win32security.error, pywintypes.error):
                continue
            if win32security.CheckTokenMembership(token, group_sid):
                return group
        return None

    def authenticateWithUsernameAndPassword(self, username, password):
        """
        Check the username and password against local accounts.
        Returns True if credentials are accepted, False otherwise.
        """
        if password is None:
            return (False, None)

        try:
            token = self._getToken(username, password)
        except (win32security.error, pywintypes.error):
            return (False, None)
        return (True, token)

    def pamWithUsernameAndPassword(self, username, password, service='login'):
        """
        Check username and password using PAM.
        """
        # PAM is not supported on Windows so this always fails.
        # Here to comply with the compat interface.
        return False

    def dropPrivileges(self, username):
        """
        Change process privileges to `username`
        On Windows this does nothing.
        """
        win32security.RevertToSelf()

    def executeAsUser(self, username=None, token=None):
        """
        Returns a context manager for changing current process privileges
        to `username`

        Raise `ChangeUserError` is there are no permissions for
        switching to user.
        """
        if username and username == self.getCurrentUserName():
            return NoOpContext()

        if token is None:
            raise ChangeUserError(
                'executeAsUser: A valid token is required.',
            )

        return _ExecuteAsUser(token)

    def getPrimaryGroup(self, username):
        """
        Return the primary group for username.
        This just returns WINDOWS_PRIMARY_GROUP.
        """
        # TODO: I don't know how to get primary group on Windows.
        # 1250

        if not self.userExists(username):
            self.raiseFailedToGetPrimaryGroup(username)
        return WINDOWS_PRIMARY_GROUP

    def _parseUPN(self, upn):
        """
        Returns a tuple of (primary_domain_controller, username) for the
        account name specified in upn format.

        Returns (None, username) is UPN does not contain a domain.
        """
        parts = upn.split('@', 1)
        if len(parts) == 2:
            primary_domain_controller = win32net.NetGetDCName(None, parts[1])
            username = parts[0]
            return (primary_domain_controller, username)
        # This is not an UPN name.
        return (None, upn)

    def _getToken(self, username, password):
        """
        Return the impersonation token for `username`.

        The `username` is specified in UPN format.
        """
        return win32security.LogonUser(
            username,
            None,
            password,
            win32security.LOGON32_LOGON_NETWORK,
            win32security.LOGON32_PROVIDER_DEFAULT,
        )


class _ExecuteAsUser:
    """
    Context manager for running under a different user.
    """

    def __init__(self, token):
        """
        Initialize the context manager.
        """
        self.token = token
        self.profile = None

    def __enter__(self):
        """
        Change process effective user.
        """
        win32security.RevertToSelf()
        win32security.ImpersonateLoggedOnUser(self.token)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        """
        Reverting previous effective ID.
        """
        win32security.RevertToSelf()
        return False


class ResetEffectivePrivilegesNTContext:
    """
    A context manager that reset the effective user.
    """

    def __enter__(self):
        """
        See class docstring.
        """
        win32security.RevertToSelf()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        """Just propagate errors."""
        return False


@implementer(IHasImpersonatedAvatar)
class NTHasImpersonatedAvatar:
    _NoOpContext = NoOpContext

    @classmethod
    def setupResetEffectivePrivileges(cls):
        """
        Does nothing on Windows.
        """
        cls._NoOpContext = ResetEffectivePrivilegesNTContext

    @property
    def use_impersonation(self):
        """
        See: :class:`IFileSystemAvatar`
        """
        raise NotImplementedError('use_impersonation')

    def getImpersonationContext(self):
        """
        See: :class:`IFileSystemAvatar`
        """
        if not self.use_impersonation:
            # Don't switch context if not required.
            return self._NoOpContext()

        return _ExecuteAsUser(token=self.token)


def get_current_username():
    """
    Name of the current username.
    """
    buffer = create_unicode_buffer(256)
    size = c_uint(len(buffer))
    while not GetUserNameW(buffer, byref(size)):
        buffer = create_unicode_buffer(len(buffer) * 2)
        size.value = len(buffer)
    return buffer.value


@implementer(IFileSystemAvatar)
class NTDefaultAvatar(NTHasImpersonatedAvatar):
    """
    Avatar for the default account.

    This is the account under which the process is executed.
    It has full access to the filesystem.
    It does not uses impersonation.
    """

    root_folder_path = 'c:\\'
    home_folder_path = 'c:\\'
    lock_in_home_folder = False
    token = None
    peer = None
    virtual_folders = ()

    @property
    def use_impersonation(self):
        """
        See: :class:`IFileSystemAvatar`
        """
        return False

    @property
    def name(self):
        """
        Name of the default avatar.
        """
        return get_current_username()


class NTSuperAvatar(NTDefaultAvatar):
    """
    On Windows, we don't have a super account so we try do our best
    using the current account.
    """
