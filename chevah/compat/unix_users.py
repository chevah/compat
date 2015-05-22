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


def _get_supplementary_groups(username_encoded):
    '''Return all groups in which `username_encoded` is a member.
    username_encoded is provided as utf-8 encoded format.
    '''
    groups = set()
    for group in grp.getgrall():
        if username_encoded in group.gr_mem:
            groups.add(group.gr_gid)
    return list(groups)


def _get_euid_and_egid(username_encoded):
    """
    Return a tuple of (euid, egid) for username.
    """
    try:
        pwnam = pwd.getpwnam(username_encoded)
    except KeyError:
        raise ChangeUserException(_(u'User does not exists.'))

    return (pwnam.pw_uid, pwnam.pw_gid)


def _change_effective_privileges(username=None, euid=None, egid=None,
                                 groups=None):
    """
    Change current process effective user and group.
    """
    if username:
        username_encoded = username.encode('utf-8')
        try:
            pwnam = pwd.getpwnam(username_encoded)
        except KeyError:
            raise ChangeUserException(_(u'User does not exists.'))
        euid = pwnam.pw_uid
        egid = pwnam.pw_gid
    else:
        assert euid is not None
        pwnam = pwd.getpwuid(euid)
        username_encoded = pwnam.pw_name

    uid, gid = os.geteuid(), os.getegid()
    if uid == euid and gid == egid:
        return

    if groups is None:
        groups = _get_supplementary_groups(username_encoded)

    try:
        if uid != 0:
            # We set root euid first to get full permissions.
            os.seteuid(0)
            os.setegid(0)

        # Make sure to set user euid as the last action. Otherwise we will no
        # longer have permissions to change egid.
        os.setgroups(groups)
        os.setegid(egid)
        os.seteuid(euid)
    except OSError:
        raise ChangeUserException(u'Could not switch user.')


class UnixUsers(CompatUsers):
    """
    Container for Unix users specific methods.
    """

    implements(IOSUsers)

    # Lazy loaded method to pam authenticate.
    _pam_authenticate = None

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

        checked = self._checkPAM(username, password)
        if checked is not None:
            if checked is True:
                return (True, None)
            else:
                # For PAM account we don't know if this is a failure due to
                # a bad credentials or non existent credentials.
                return (None, None)

        return (None, None)

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
        '''Authenticate against the /etc/passwd file.

        Return False if user was not found or password is wrong.
        Returns None if password is stored in shadow file.
        '''
        username = username.encode('utf-8')
        password = password.encode('utf-8')
        try:
            with self._executeAsAdministrator():
                crypted_password = pwd.getpwnam(username)[1]
            # On OSX the crypted_password is returned as '********'.
            if '**' in crypted_password:
                crypted_password = '*'
        except KeyError:
            return None
        else:
            if crypted_password in ('*', 'x'):
                # Allow other methods to take over if password is not
                # stored in passwd file.
                return None
            provided_password = crypt.crypt(
                password, crypted_password)
            if crypted_password == provided_password:
                return True
        return False

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

        def get_crypted_password(password, salt):
            '''Return the crypted password based on salt.

            salt can be an salted password.
            '''
            crypt_value = crypt.crypt(password, salt)
            if os.sys.platform == 'sunos5' and crypt_value.startswith('$6$'):
                # There is a bug in Python 2.5 and crypt add some extra
                # values for shadow passwords of type 6.
                crypt_value = crypt_value[:12] + crypt_value[20:]
            return crypt_value

        try:
            with self._executeAsAdministrator():
                crypted_password = spwd.getspnam(username).sp_pwd

            # Locked account
            if crypted_password in ('LK'):
                return False

            # Also locked account but LDAP accounts are listed on Ubuntu
            # `getent shadow` with password '*', even if they are active.
            if crypted_password in ('*'):
                return None

            # Allow other methods to take over if password is not
            # stored in shadow file.
            # NP is added by Centrify.
            if crypted_password in ('!', 'x', 'NP'):
                return None
        except KeyError:
            return None
        else:
            provided_password = get_crypted_password(
                password, crypted_password)
            if crypted_password == provided_password:
                return True
        return False

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

    def _checkPAM(self, username, password):
        """
        Authenticate against PAM library.
        """
        pam_authenticate = self._getPAMAuthenticate()
        if not pam_authenticate:
            return None

        # On Python2.7/OSX PAM require str not bytes.
        username = codecs.encode(username, 'utf-8')
        password = codecs.encode(password, 'utf-8')
        with self._executeAsAdministrator():
            return pam_authenticate(username, password)


class _ExecuteAsUser(object):
    '''Context manager for running under a different user.'''

    def __init__(self, username=None, euid=0, egid=0, groups=None):
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
        self.groups = groups
        self.initial_euid = os.geteuid()
        self.initial_egid = os.getegid()
        self.initial_groups = os.getgroups()

    def __enter__(self):
        '''Change process effective user.'''
        _change_effective_privileges(
            euid=self.euid, egid=self.egid, groups=self.groups)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        '''Reverting previous effective ID.'''
        _change_effective_privileges(
            euid=self.initial_euid,
            egid=self.initial_egid,
            groups=self.initial_groups,
            )
        return False


class UnixHasImpersonatedAvatar(object):

    implements(IHasImpersonatedAvatar)

    _groups = None
    _euid = None
    _egid = None

    def __init__(self):
        self._euid = None
        self._egid = None
        self._groups = None

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
            self._groups = _get_supplementary_groups(username_encoded)

        return _ExecuteAsUser(
            euid=self._euid,
            egid=self._egid,
            groups=self._groups,
            )


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
