# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
"""
Adapter for working with Unix users.
"""

import crypt
import grp
import os
import pwd

try:
    import spwd

    HAS_SHADOW_SUPPORT = True
except ImportError:
    HAS_SHADOW_SUPPORT = False

from zope.interface import implementer

from chevah_compat.compat_users import CompatUsers
from chevah_compat.exceptions import ChangeUserError
from chevah_compat.helpers import NoOpContext, _
from chevah_compat.interfaces import (
    IFileSystemAvatar,
    IHasImpersonatedAvatar,
    IOSUsers,
)

_GLOBAL_EUID = os.geteuid()
_GLOBAL_EGID = os.getegid()


def _get_euid_and_egid(username):
    """
    Return a tuple of (euid, egid) for username.
    """
    try:
        pwnam = pwd.getpwnam(username)
    except KeyError:
        raise ChangeUserError('Username does not exists.')

    return (pwnam.pw_uid, pwnam.pw_gid)


def _change_effective_privileges(username=None, euid=None, egid=None):
    """
    Change current process effective user and group.
    """
    if username:
        try:
            pwnam = pwd.getpwnam(username)
        except KeyError:
            raise ChangeUserError('User does not exists.')
        euid = pwnam.pw_uid
        egid = pwnam.pw_gid
    else:
        if euid is None:
            raise ChangeUserError(
                'You need to pass euid when username is not passed.',
            )
        pwnam = pwd.getpwuid(euid)
        username = pwnam.pw_name

    uid, gid = os.geteuid(), os.getegid()
    if uid == euid and gid == egid:
        # We are already under the requested user.
        return

    try:
        if uid != 0:
            # We set root euid first to get full permissions.
            os.seteuid(0)
            os.setegid(0)

        # Make sure to set user euid as the last action. Otherwise we will no
        # longer have permissions to change egid.
        os.initgroups(username, egid)
        os.setegid(egid)
        os.seteuid(euid)
    except OSError:
        raise ChangeUserError('Could not switch user.')


def _verifyCrypt(password, crypted_password):
    """
    Return `True` if password can be associated with `crypted_password`,
    and return `False` otherwise.
    """
    provided_password = crypt.crypt(password, crypted_password)

    if os.sys.platform == 'sunos5' and provided_password.startswith('$6$'):
        # There is a bug in Python 2.5 and crypt add some extra
        # values for shadow passwords of type 6.
        provided_password = provided_password[:12] + provided_password[20:]

    if provided_password == crypted_password:
        return True

    return False


@implementer(IOSUsers)
class UnixUsers(CompatUsers):
    """
    Container for Unix users specific methods.
    """

    # Lazy loaded method to pam authenticate.
    _pam_authenticate = None

    # Values which mark that password is stored somewhere.
    # `*` is for denied accounts but it is also used for LDAP accounts
    # which are listed on Ubuntu `getent shadow` with password '*', even if
    # they are active.
    # `NP` is Centrify way of saying `*NP*`.
    _NOT_HERE = ('x', 'NP', '*NP*', '*')

    def getCurrentUserName(self):
        """
        Return the name of the account under which the current
        process is executed.
        """
        return pwd.getpwuid(os.geteuid()).pw_name

    def getHomeFolder(self, username, token=None):
        """Get home folder for local (or NIS) user."""
        try:
            home_folder = pwd.getpwnam(username).pw_dir
            return home_folder.rstrip('/')
        except KeyError:
            self.raiseFailedToGetHomeFolder(username, _('Username not found.'))

    def userExists(self, username):
        """
        Returns `True` if username exists on this system.
        """
        # OSX return an user with uid and gid 0 for empty user.
        if not username:
            return False

        try:
            pwd.getpwnam(username)
        except KeyError:
            return False
        except Exception as error:
            self.raiseFailedtoCheckUserExists(username, str(error))

        return True

    def getGroupForUser(self, username, groups, token=None):
        """
        See: IOSUsers

        It matches groups based on both name and group ID.
        """
        if not groups:
            raise ValueError("Groups for validation can't be empty.")

        for group in groups:
            try:
                group_struct = grp.getgrnam(group)
            except KeyError:
                continue

            try:
                user_struct = pwd.getpwnam(username)
            except KeyError:
                # Unknown user.
                return None

            if user_struct.pw_gid == group_struct.gr_gid:
                # Match on group ID.
                return group

            if username in group_struct.gr_mem:
                # Match on group name.
                return group

        return None

    def authenticateWithUsernameAndPassword(self, username, password):
        """
        Check the username and password against local accounts.

        Returns True if credentials are accepted, False otherwise.
        Returns `None` if credentials are not defined in the
        /etc/passwd or the /etc/shadow files.
        """
        checked = self._checkPasswdFile(username, password)
        if checked is not None:
            if checked is True:
                return (True, None)
            return (False, None)

        checked = self._checkShadowFile(username, password)
        if checked is not None:
            if checked is True:
                return (True, None)
            return (False, None)

        checked = self._checkShadowDBFile(username, password)
        if checked is not None:
            if checked is True:
                return (True, None)
            return (False, None)

        return (None, None)

    def pamWithUsernameAndPassword(self, username, password, service='login'):
        """
        Check username and password using PAM.

        Returns True if credentials are accepted, False otherwise.
        """
        pam_authenticate = self._getPAMAuthenticate()
        if not pam_authenticate:
            # PAM is not supported.
            return False

        with self._executeAsAdministrator():
            # Some PAM modules and some PAM setups might not need root.
            # Most of the time, PAM is configured as a proxy for /etc/shadow
            # and in this case root is required.
            checked = pam_authenticate(username, password, service)

        if checked is True:
            return True

        # For PAM account we don't know if this is a failure due to
        # a bad credentials or non existent credentials.
        # Credentials are always rejected.
        return False

    def pamOnlyWithUsernameAndPassword(
        self, username, password, service='login'
    ):
        """
        Check username and password using only PAM and using the current
        service user.

        No root is required.

        Event if users and passwords are valid, this might fail, depending
        on PAM configuration.

        Returns True if credentials are accepted, False otherwise.
        """
        from pam import authenticate as pam_authenticate

        try:
            checked = pam_authenticate(username, password, service)
        except AttributeError:
            raise ChangeUserError('PAM is not available.')

        if checked is True:
            return True

        # For PAM account we don't know if this is a failure due to
        # a bad credentials or non existent credentials.
        # Credentials are always rejected.
        return False

    def dropPrivileges(self, username):
        """Change process privileges to `username`.

        Raise `ChangeUserError` is there are no permissions for
        switching to user.
        """
        global _GLOBAL_EUID, _GLOBAL_EGID

        _change_effective_privileges(username)

        # Record the new default user.
        _GLOBAL_EUID = os.geteuid()
        _GLOBAL_EGID = os.getegid()

    def executeAsUser(self, username, token=None):
        """
        Returns a context manager for chaning current process privileges
        to `username`.

        Raise `ChangeUserError` is there are no permissions for
        switching to user or user does not exists.
        """
        return _ExecuteAsUser(username=username)

    def getPrimaryGroup(self, username):
        """Return get primary group for avatar."""
        try:
            user_struct = pwd.getpwnam(username)
            group_struct = grp.getgrgid(user_struct.pw_gid)
        except KeyError:
            self.raiseFailedToGetPrimaryGroup(username)
        return group_struct.gr_name

    def _executeAsAdministrator(self):
        """Returns a context manager for running under administrator user.

        Raise `ChangeUserError` is there are no permissions for
        switching to user.
        """
        return _ExecuteAsUser(euid=0, egid=0)

    def _checkPasswdFile(self, username, password):
        """
        Authenticate against the /etc/passwd file.

        Return False if user was not found or password is wrong.
        Returns None if password is stored in shadow file.
        """
        from chevah_compat import process_capabilities

        username = username
        password = password

        try:
            # Crypted password should be readable to all users.
            # With the exception of AIX which has /etc/security/passwd to
            # store passwd and that file is only readable by root.
            if process_capabilities.os_name == 'aix':
                with self._executeAsAdministrator():
                    crypted_password = pwd.getpwnam(username)[1]
            else:
                crypted_password = pwd.getpwnam(username)[1]
        except KeyError:
            # User does not exists.
            return None

        if process_capabilities.os_name == 'osx' and '**' in crypted_password:
            # On OSX the crypted_password is returned as '********'.
            crypted_password = 'x'

        if crypted_password in self._NOT_HERE:
            # Allow other methods to take over if password is not
            # stored in passwd.
            return None

        return _verifyCrypt(password, crypted_password)

    def _checkShadowFile(self, username, password):
        """
        Authenticate against /etc/shadow file.

        salt and hashed password OR a status exception value e.g.:
            * "$id$salt$hashed", where "$id" is the algorithm used:
             * "$1$" stands for MD5
             * "$2$" is Blowfish
             * "$5$" is SHA-256 and "$6$" is SHA-512
             * check "crypt" manpage

            * "NP" or "!" or null - No password, the account has no password
            * "LK" or "*" - the account is Locked,
               user will be unable to log-in
            * "!!" - the password has expired
        """
        if not HAS_SHADOW_SUPPORT:
            return None

        username = username
        password = password

        try:
            with self._executeAsAdministrator():
                crypted_password = spwd.getspnam(username).sp_pwd

            # Locked account
            if crypted_password in ('LK',):
                return False

            # Allow other methods to take over if password is not
            # stored in shadow file.
            if crypted_password in self._NOT_HERE:
                return None
        except KeyError:
            return None

        return _verifyCrypt(password, crypted_password)

    def _checkShadowDBFile(self, username, password):
        """
        Authenticate against /etc/spwd.db BSD file.
        """
        from chevah_compat import process_capabilities

        if process_capabilities.os_name not in ['freebsd', 'openbsd']:
            return None

        # For now we don't support py3.
        import bsddb185  # pylint: disable=bad-python3-import

        username = username.encode('utf-8')
        password = password.encode('utf-8')

        entry = ''
        db = None

        # We try to keep the context switch as little as possible.
        try:
            with self._executeAsAdministrator():
                db = bsddb185.open('/etc/spwd.db')

            try:
                entry = db['1' + username]
            except KeyError:
                return None

        finally:
            if db:
                db.close()

        parts = entry.split('\x00')

        if len(parts) > 2:
            crypted_password = parts[1]
        else:
            return False

        return _verifyCrypt(password, crypted_password)

    def _getPAMAuthenticate(self):
        """
        FIXME:1848:
        Lazy loading of pam library to mitigate module loading side effects
        on AIX.
        """
        # We check for explicit None as this means that import was not tried.
        if self._pam_authenticate is None:
            # Runtime PAM support was not checked yet.

            try:
                from pam import authenticate as pam_authenticate

                self._pam_authenticate = pam_authenticate
            except (ImportError, AssertionError):
                # We set this to false to not check it again.
                # On macOS we get AssertionError when failing to load.
                self._pam_authenticate = False

        return self._pam_authenticate


class _ExecuteAsUser:
    """
    Context manager for running under a different user.
    """

    def __init__(self, username=None, euid=0, egid=0):
        """Initialize the context manager."""
        if username is not None:
            try:
                pwnam = pwd.getpwnam(username)
            except KeyError:
                raise ChangeUserError('User does not exists.')
            euid = pwnam.pw_uid
            egid = pwnam.pw_gid
        self.euid = euid
        self.egid = egid
        self._initial_euid = os.geteuid()
        self._initial_egid = os.getegid()

    def __enter__(self):
        """
        Change process effective user.
        """
        _change_effective_privileges(euid=self.euid, egid=self.egid)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        """
        Reverting to the default effective ID.
        """
        _change_effective_privileges(
            euid=self._initial_euid,
            egid=self._initial_egid,
        )
        return False


class ResetEffectivePrivilegesUnixContext:
    """
    A context manager that reset the effecit user.
    """

    def __enter__(self):
        """
        See class docstring.
        """
        _change_effective_privileges(
            euid=_GLOBAL_EUID,
            egid=_GLOBAL_EGID,
        )
        return self

    def __exit__(self, exc_type, exc_value, tb):
        """Just propagate errors."""
        return False


@implementer(IHasImpersonatedAvatar)
class UnixHasImpersonatedAvatar:
    _euid = None
    _egid = None

    _NoOpContext = NoOpContext

    def __init__(self):
        self._euid = None
        self._egid = None

    @classmethod
    def setupResetEffectivePrivileges(cls):
        cls._NoOpContext = ResetEffectivePrivilegesUnixContext

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
            return self._NoOpContext()

        # Create cached values if not initialized.
        if not (self._euid and self._egid):
            (self._euid, self._egid) = _get_euid_and_egid(self.name)

        return _ExecuteAsUser(euid=self._euid, egid=self._egid)


@implementer(IFileSystemAvatar)
class UnixDefaultAvatar(UnixHasImpersonatedAvatar):
    """
    Avatar for the default account.

    This is the account under which the process is executed.
    It has full access to the filesystem.
    It does not use impersonation.
    """

    home_folder_path = '/'
    root_folder_path = '/'
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
        return pwd.getpwuid(os.getuid()).pw_name


@implementer(IFileSystemAvatar)
class UnixSuperAvatar(UnixHasImpersonatedAvatar):
    """
    Avatar for the super account on Unix aka root.
    """

    home_folder_path = '/root'
    root_folder_path = '/'
    lock_in_home_folder = False
    token = None
    peer = None
    virtual_folders = ()

    @property
    def use_impersonation(self):
        """
        See: :class:`IFileSystemAvatar`
        """
        return True

    @property
    def name(self):
        """
        Name of the default avatar.
        """
        return 'root'
