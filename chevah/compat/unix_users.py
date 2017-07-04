# Copyright (c) 2010 Adi Roiban.
# See LICENSE for details.
"""
Adapter for working with Unix users.
"""
from __future__ import with_statement
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
# On Python2.7 grp module does no accept bytes so we use the codecs module
# to convert Unicode to native str.
import codecs
import crypt
import grp
import os
import pwd

try:
    import spwd
    HAS_SHADOW_SUPPORT = True
except ImportError:
    HAS_SHADOW_SUPPORT = False

from zope.interface import implements

from chevah.compat.compat_users import CompatUsers
from chevah.compat.exceptions import ChangeUserException
from chevah.compat.helpers import (
    _,
    NoOpContext,
    )
from chevah.compat.interfaces import (
    IFileSystemAvatar,
    IHasImpersonatedAvatar,
    IOSUsers,
    )


def _get_euid_and_egid(username_encoded):
    """
    Return a tuple of (euid, egid) for username.
    """
    try:
        pwnam = pwd.getpwnam(username_encoded)
    except KeyError:
        raise ChangeUserException(_(u'User does not exists.'))

    return (pwnam.pw_uid, pwnam.pw_gid)


def _change_effective_privileges(username=None, euid=None, egid=None):
    """
    Change current process effective user and group.
    """
    if username:
        username_encoded = username.encode('utf-8')
        try:
            pwnam = pwd.getpwnam(username_encoded)
        except KeyError:
            raise ChangeUserException(u'User does not exists.')
        euid = pwnam.pw_uid
        egid = pwnam.pw_gid
    else:
        if euid is None:
            raise ChangeUserException(
                'You need to pass euid when username is not passed.')
        pwnam = pwd.getpwuid(euid)
        username_encoded = pwnam.pw_name

    uid, gid = os.geteuid(), os.getegid()
    if uid == euid and gid == egid:
        return

    try:
        if uid != 0:
            # We set root euid first to get full permissions.
            os.seteuid(0)
            os.setegid(0)

        # Make sure to set user euid as the last action. Otherwise we will no
        # longer have permissions to change egid.
        os.initgroups(username_encoded, egid)
        os.setegid(egid)
        os.seteuid(euid)
    except OSError:
        raise ChangeUserException(u'Could not switch user.')


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


class UnixUsers(CompatUsers):
    """
    Container for Unix users specific methods.
    """

    implements(IOSUsers)

    # Lazy loaded method to pam authenticate.
    _pam_authenticate = None

    # Values which mark that password is stored somewhere.
    # `*` is for denied accounts but it is also used for LDAP accounts
    # which are listed on Ubuntu `getent shadow` with password '*', even if
    # they are active.
    # `NP` is Centrify way of saying `*NP*`.
    _NOT_HERE = ('x', 'NP', '*NP*', '*')

    def getHomeFolder(self, username, token=None):
        '''Get home folder for local (or NIS) user.'''
        try:
            username_encoded = username.encode('utf-8')
            home_folder = pwd.getpwnam(
                username_encoded).pw_dir.decode('utf-8')
            return home_folder
        except KeyError:
            self.raiseFailedToGetHomeFolder(
                username, _(u'Username not found.'))

    def userExists(self, username):
        """
        Returns `True` if username exists on this system.
        """
        # OSX return an user with uid and gid 0 for empty user.
        if not username:
            return False

        username = username.encode('utf-8')
        try:
            pwd.getpwnam(username)
        except KeyError:
            return False
        return True

    def isUserInGroups(self, username, groups, token=None):
        '''Return true if `username` is a member of `groups`.'''
        username_encode = username.encode('utf-8')
        for group in groups:
            group_name = codecs.encode(group, 'utf-8')
            try:
                group_struct = grp.getgrnam(group_name)
            except KeyError:
                continue

            try:
                user_struct = pwd.getpwnam(username_encode)
            except KeyError:
                # Unknown user.
                return False

            if user_struct.pw_gid == group_struct.gr_gid:
                return True

            if username_encode in group_struct.gr_mem:
                return True
        return False

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
            else:
                return (False, None)

        checked = self._checkShadowFile(username, password)
        if checked is not None:
            if checked is True:
                return (True, None)
            else:
                return (False, None)

        checked = self._checkShadowDBFile(username, password)
        if checked is not None:
            if checked is True:
                return (True, None)
            else:
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

        # On Python2.7/OSX PAM require str not bytes.
        username = codecs.encode(username, 'utf-8')
        password = codecs.encode(password, 'utf-8')

        with self._executeAsAdministrator():
            # FIXME:3059:
            # PAM can be used without admin right but I have no idea why
            # it fails with errors like:
            # audit_log_acct_message() failed: Operation not permitted.
            checked = pam_authenticate(username, password, service)

        if checked is True:
            return True

        # For PAM account we don't know if this is a failure due to
        # a bad credentials or non existent credentials.
        # Credentials are always rejected.
        return False

    def dropPrivileges(self, username):
        '''Change process privileges to `username`.

        Return `ChangeUserException` is there are no permissions for
        switching to user.
        '''
        _change_effective_privileges(username)

    def executeAsUser(self, username, token=None):
        """
        Returns a context manager for chaning current process privileges
        to `username`.

        Return `ChangeUserException` is there are no permissions for
        switching to user or user does not exists.
        """
        return _ExecuteAsUser(username=username)

    def getPrimaryGroup(self, username):
        '''Return get primary group for avatar.'''
        username_encode = username.encode('utf-8')
        try:
            user_struct = pwd.getpwnam(username_encode)
            group_struct = grp.getgrgid(user_struct.pw_gid)
        except KeyError:
            self.raiseFailedToGetPrimaryGroup(username)
        group_name = group_struct.gr_name
        return group_name.decode('utf-8')

    def _executeAsAdministrator(self):
        '''Returns a context manager for running under administrator user.

        Return `ChangeUserException` is there are no permissions for
        switching to user.
        '''
        return _ExecuteAsUser(euid=0, egid=0)

    def _checkPasswdFile(self, username, password):
        """
        Authenticate against the /etc/passwd file.

        Return False if user was not found or password is wrong.
        Returns None if password is stored in shadow file.
        """
        from chevah.compat import process_capabilities

        username = username.encode('utf-8')
        password = password.encode('utf-8')

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
        '''
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
        '''
        if not HAS_SHADOW_SUPPORT:
            return None

        username = username.encode('utf-8')
        password = password.encode('utf-8')

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
        from chevah.compat import process_capabilities
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

            from chevah.compat import process_capabilities
            if process_capabilities.os_name == 'hpux':
                # FIXME:2745:
                # Ctypes and pam are broken on HPUX.
                self._pam_authenticate = False
                return self._pam_authenticate

            try:
                from pam import authenticate as pam_authenticate
                self._pam_authenticate = pam_authenticate
            except ImportError:
                # We set this to false to not check it again.
                self._pam_authenticate = False

        return self._pam_authenticate


class _ExecuteAsUser(object):
    '''Context manager for running under a different user.'''

    def __init__(self, username=None, euid=0, egid=0):
        '''Initialize the context manager.'''
        if username is not None:
            try:
                pwnam = pwd.getpwnam(username.encode('utf-8'))
            except KeyError:
                raise ChangeUserException(_(u'User does not exists.'))
            euid = pwnam.pw_uid
            egid = pwnam.pw_gid
        self.euid = euid
        self.egid = egid
        self.initial_euid = os.geteuid()
        self.initial_egid = os.getegid()

    def __enter__(self):
        '''Change process effective user.'''
        _change_effective_privileges(euid=self.euid, egid=self.egid)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        '''Reverting previous effective ID.'''
        _change_effective_privileges(
            euid=self.initial_euid, egid=self.initial_egid)
        return False


class UnixHasImpersonatedAvatar(object):

    implements(IHasImpersonatedAvatar)

    _euid = None
    _egid = None

    def __init__(self):
        self._euid = None
        self._egid = None

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
            return NoOpContext()

        # Create cached values if not initialized.
        if not (self._euid and self._egid):
            username_encoded = self.name.encode('utf-8')
            (self._euid, self._egid) = _get_euid_and_egid(username_encoded)

        return _ExecuteAsUser(euid=self._euid, egid=self._egid)


class UnixDefaultAvatar(UnixHasImpersonatedAvatar):
    """
    Avatar for the default account.

    This is the account under which the process is executed.
    It has full access to the filesystem.
    It does not use impersonation.
    """

    implements(IFileSystemAvatar)

    home_folder_path = '/'
    root_folder_path = '/'
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
        return pwd.getpwuid(os.getuid()).pw_name


class UnixSuperAvatar(UnixHasImpersonatedAvatar):
    """
    Avatar for the super account on Unix aka root.
    """

    implements(IFileSystemAvatar)

    home_folder_path = u'/root'
    root_folder_path = '/'
    lock_in_home_folder = False
    token = None
    peer = None

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
