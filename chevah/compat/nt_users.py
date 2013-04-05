# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Adapter for working with NT users.'''
from __future__ import with_statement

from win32com.shell import shell, shellcon
from zope.interface import implements
import pythoncom
import win32net
import win32profile
import win32security

from chevah.compat.constants import WINDOWS_PRIMARY_GROUP
from chevah.compat.exceptions import (
    ChangeUserException,
    CompatError,
    )
from chevah.compat.helpers import (
    _,
    NoOpContext,
    raise_failed_to_get_home_folder,
    raise_failed_to_get_primary_group,
    )
from chevah.compat.interfaces import (
    IFileSystemAvatar,
    IHasImpersonatedAvatar,
    IOSUsers,
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


class NTUsers(object):
    '''Container for NT users specific methods.'''

    implements(IOSUsers)

    def getCurrentUserName(self):
        """
        The name of current user.
        """
        return get_current_username()

    def getHomeFolder(self, username, token=None):
        '''Get home folder for local user.'''
        # In windows, you can choose to care about local versus
        # roaming profiles.
        # You can fetch the current user's through PyWin32.
        #
        # For example, to ask for the roaming 'Application Data' directory:
        #  (CSIDL_APPDATA asks for the roaming,
        #   CSIDL_LOCAL_APPDATA for the local one)
        #  (See microsoft references for further CSIDL constants)
        #  http://msdn.microsoft.com/en-us/library/bb762181(VS.85).aspx

        # Force creation of local profile so that we can query the home
        # folder.

        if not process_capabilities.get_home_folder:
            message = (
                u'Operating system does not support getting home folder '
                u'for account "%s"' % (username))
            raise_failed_to_get_home_folder(username, message)

        home_folder_path = None

        def _getHomeFolderPath():
            with self.executeAsUser(
                    username=username, token=token):
                try:
                    CSIDL_FLAG_CREATE = 0x8000
                    path = shell.SHGetFolderPath(
                        0,
                        shellcon.CSIDL_PROFILE | CSIDL_FLAG_CREATE,
                        token,
                        0,
                        )
                    return path
                except pythoncom.com_error, (number, message, e1, e2):
                    error_text = _(u'%d:%s' % (number, message))
                    raise_failed_to_get_home_folder(username, error_text)

        def _createProfile():
            try:
                self._createLocalProfile(username, token)
            except win32security.error, (error_id, error_call, error_message):
                error_text = _(
                    u'Failed to create user profile. '
                    u'Make sure you have SeBackupPrivilege and '
                    u'SeRestorePrivilege. (%d:%s - %s)' % (
                        error_id, error_call, error_message))
                raise_failed_to_get_home_folder(username, error_text)

        try:
            try:
                # Get home folder if profile already exists.
                home_folder_path = _getHomeFolderPath()
            except CompatError:
                # On erros we try to create the profile
                # and try one last time.
                _createProfile()
                home_folder_path = _getHomeFolderPath()
        except ChangeUserException, error:
            # We fail to impersoante the user, so we exit early.
            raise_failed_to_get_home_folder(username, error.message)

        if home_folder_path:
            return home_folder_path
        else:
            # Maybe this should be an AssertionError since we should not
            # arrive here.
            raise_failed_to_get_home_folder(
                    username,
                    _(u'Failed to get home folder path.'),
                    )

    def userExists(self, username):
        '''Returns `True` if username exists on this system.'''
        # Windows is stupid and return True for empty user.
        # Even when guest account is disabled.
        if not username:
            return False
        try:
            win32security.LookupAccountName('', username)
            return True
        except win32security.error, (number, name, messsage):
            if number == 1332:
                return False
            else:
                raise

    def isUserInGroups(self, username, groups, token):
        '''Return true if `username` is a member of `groups`.'''
        for group in groups:
            try:
                group_sid, group_domain, group_type = (
                    win32security.LookupAccountName(None, group))
            except win32security.error:
                continue
            if win32security.CheckTokenMembership(token, group_sid):
                return True
        return False

    def authenticateWithUsernameAndPassword(self, username, password):
        '''Check the username and password agains local accounts.

        Returns True if credentials are accepted, False otherwise.
        '''
        if password is None:
            return (False, None)

        try:
            token = self._getToken(username, password)
        except win32security.error:
            return (False, None)
        return (True, token)

    def dropPrivileges(self, username):
        '''Change process privileges to `username`.

        On Windows this does nothing.
        '''
        win32security.RevertToSelf()

    def executeAsUser(self, username=None, token=None):
        '''Returns a context manager for chaning current process privileges
        to `username`.

        Return `ChangeUserException` is there are no permissions for
        switching to user.
        '''
        if username and username == self.getCurrentUserName():
            return NoOpContext()

        if token is None:
            raise ChangeUserException(
                u'executeAsUser: A valid token is required.')

        return _ExecuteAsUser(token)

    def getPrimaryGroup(self, username):
        '''Return the primary group for username.'''
        if not self.userExists(username):
            raise_failed_to_get_primary_group(username)
        return WINDOWS_PRIMARY_GROUP

    def _createLocalProfile(self, username, token):
        '''Create the local profile if it does not exists.'''

        domain, name = self._parseUPN(username)

        user_info_4 = win32net.NetUserGetInfo(domain, name, 4)
        profile_path = user_info_4['profile']
        # LoadUserProfile apparently doesn't like an empty string.
        if not profile_path:
            profile_path = None

        profile = win32profile.LoadUserProfile(
            token,
            {
                'UserName': name,
                'ServerName': domain,
                'Flags': 0,
                'ProfilePath': profile_path,
            })
        win32profile.UnloadUserProfile(token, profile)
        return True

    def _parseUPN(self, upn):
        """
        Return domain and username for UPN username format.

        Return (None, username) is UPN does not contain a domain.
        """
        parts = upn.split('@', 1)
        if len(parts) == 2:
            domain = win32net.NetGetDCName(None, parts[1])
            username = parts[1]
            return (domain, username)
        else:
            # This is not an UPN name.
            return (None, upn)

    def _getToken(self, username, password):
        '''Return user token.'''
        return win32security.LogonUser(
            username,
            None,
            password,
            win32security.LOGON32_LOGON_NETWORK,
            win32security.LOGON32_PROVIDER_DEFAULT,
            )


class _ExecuteAsUser(object):
    '''Context manager for running under a different user.'''

    def __init__(self, token):
        '''Initialize the context manager.'''
        self.token = token
        self.profile = None

    def __enter__(self):
        '''Change process effective user.'''
        win32security.RevertToSelf()
        win32security.ImpersonateLoggedOnUser(self.token)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        '''Reverting previous effective ID.'''
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
