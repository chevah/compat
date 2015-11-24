# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Adapter for working with NT users.
"""
from __future__ import with_statement
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from win32com.shell import shell, shellcon
from zope.interface import implements
import pythoncom
import win32net
import win32profile
import win32security

from chevah.compat.compat_users import CompatUsers
from chevah.compat.constants import (
    CSIDL_FLAG_CREATE,
    WINDOWS_PRIMARY_GROUP,
    )
from chevah.compat.exceptions import (
    ChangeUserException,
    )
from chevah.compat.helpers import NoOpContext
from chevah.compat.interfaces import (
    IFileSystemAvatar,
    IHasImpersonatedAvatar,
    IOSUsers,
    )
from chevah.compat.winerrors import (
    ERROR_NONE_MAPPED,
    )
# We can not import chevah.compat.process_capabilities as it would
# create a circular import.
from chevah.compat.nt_capabilities import NTProcessCapabilities

from ctypes import (
    windll, c_wchar_p, c_uint, POINTER, byref, create_unicode_buffer)

advapi32 = windll.advapi32
GetUserNameW = advapi32.GetUserNameW
GetUserNameW.argtypes = [c_wchar_p, POINTER(c_uint)]
GetUserNameW.restype = c_uint

# This is initialized at this module level so that it can be reuse in the
# whole module as a normal import from chevah.compat.
process_capabilities = NTProcessCapabilities()


class MissingProfileFolderException(Exception):
    """
    Non existing user profile folder exception.
    """


class NTUsers(CompatUsers):
    """
    Container for NT users specific methods.
    """

    implements(IOSUsers)

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
        # FIXME:2119:
        # Replace with decorator that will raise an exception when
        # insufficient capabilities.
        if not process_capabilities.get_home_folder:
            message = (
                u'Operating system does not support getting home folder '
                u'for account "%s".' % username)
            self.raiseFailedToGetHomeFolder(username, message)

        try:
            if token is None:
                if username != self.getCurrentUserName():
                    self.raiseFailedToGetHomeFolder(
                        username, u'Invalid username/token combination.')
                return self._getHomeFolderPath()
            else:
                return self._getHomeFolder(username, token)
        except MissingProfileFolderException:
                self.raiseFailedToGetHomeFolder(
                    username, u'Failed to get home folder path.')

    def _getHomeFolder(self, username, token):
        """
        Return home folder for specified `username` and `token`.
        """
        def _safe_get_home_path():
            try:
                with self.executeAsUser(username, token):
                    return self._getHomeFolderPath(token)
            except ChangeUserException as error:
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
            return path
        except pythoncom.com_error:
            raise MissingProfileFolderException()

    def _createLocalProfile(self, username, token):
        """
        Create the local profile for specified `username`.
        """
        try:
            primary_domain_controller, name = self._parseUPN(username)

            user_info_4 = win32net.NetUserGetInfo(
                primary_domain_controller, name, 4)

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
        except win32security.error as error:
            (error_id, error_call, error_message) = error
            error_text = (
                u'Failed to create user profile. '
                u'Make sure you have SeBackupPrivilege and '
                u'SeRestorePrivilege. (%d: %s - %s)' % (
                    error_id, error_call, error_message))
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
            return True
        except win32security.error as error:
            (number, name, message) = error
            if number == ERROR_NONE_MAPPED:
                return False
            else:
                raise

    def isUserInGroups(self, username, groups, token):
        """
        Return true if `username` is a member of `groups`.
        """
        primary_domain_controller, name = self._parseUPN(username)

        for group in groups:
            try:
                group_sid, group_domain, group_type = (
                    win32security.LookupAccountName(
                        primary_domain_controller, group))
            except win32security.error:
                continue
            if win32security.CheckTokenMembership(token, group_sid):
                return True
        return False

    def authenticateWithUsernameAndPassword(self, username, password):
        """
        Check the username and password against local accounts.
        Returns True if credentials are accepted, False otherwise.
        """
        if password is None:
            return (False, None)

        try:
            token = self._getToken(username, password)
        except win32security.error:
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
        Return `ChangeUserException` is there are no permissions for
        switching to user.
        """
        if username and username == self.getCurrentUserName():
            return NoOpContext()

        if token is None:
            raise ChangeUserException(
                u'executeAsUser: A valid token is required.')

        return _ExecuteAsUser(token)

    def getPrimaryGroup(self, username):
        """
        Return the primary group for username.
        This just returns WINDOWS_PRIMARY_GROUP.
        """
        # FIXME:1250:
        # I don't know how to get primary group on Windows.
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
        else:
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


class _ExecuteAsUser(object):
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


class NTHasImpersonatedAvatar(object):

    implements(IHasImpersonatedAvatar)

    @property
    def use_impersonation(self):
        """
        See: :class:`IFileSystemAvatar`
        """
        raise NotImplementedError()

    def getImpersonationContext(self):
        """
        See: :class:`IFileSystemAvatar`
        """
        if not self.use_impersonation:
            # Don't switch context if not required.
            return NoOpContext()

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


class NTDefaultAvatar(NTHasImpersonatedAvatar):
    """
    Avatar for the default account.

    This is the account under which the process is executed.
    It has full access to the filesystem.
    It does not uses impersonation.
    """

    implements(IFileSystemAvatar)

    root_folder_path = u'c:\\'
    home_folder_path = u'c:\\'
    lock_in_home_folder = False
    token = None
    peer = None

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
