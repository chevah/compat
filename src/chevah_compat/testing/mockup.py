"""
Module containing helpers for testing the Chevah project.
"""

import os
import random
import string
import uuid

import six
from unidecode import unidecode

try:
    from twisted.internet.protocol import Factory
    from twisted.internet.tcp import Port
except ImportError:  # pragma: no cover
    # Twisted support is optional.
    pass

from chevah_compat import DefaultAvatar, process_capabilities, system_users
from chevah_compat.avatar import FilesystemApplicationAvatar, FilesystemOSAvatar
from chevah_compat.testing.constant import TEST_NAME_MARKER
from chevah_compat.testing.filesystem import LocalTestFilesystem


def _sanitize_name_legacy_unix(candidate):
    """
    Return valid user/group name for old Unix (AIX/HPUX) from `candidate`.

    By default password is limited to 8 characters without spaces.
    """
    return unidecode(candidate).replace(' ', '_')[:8]


def _sanitize_name_windows(candidate):
    """
    Return valid user/group name for Windows OSs from `candidate.
    """
    # TODO: On Windows, we can't delete home folders with unicode names.
    # 927

    return unidecode(candidate)


class SanitizeNameMixin:
    @classmethod
    def sanitizeName(cls, name):
        """
        Return name sanitized for current OS.
        """
        from chevah_compat.testing.testcase import ChevahTestCase

        os_name = process_capabilities.os_name
        os_version = ChevahTestCase.os_version
        if os_name in ['aix', 'hpux', 'freebsd', 'openbsd']:
            return _sanitize_name_legacy_unix(name)
        if os_version in ['osx-10.16']:
            # It looks like macOS 11 can't handle full Unix group names.
            macosname = _sanitize_name_legacy_unix(name)
            return macosname.replace('_', 'Z')
        if os_name == 'windows':
            return _sanitize_name_windows(name)

        return name


class TestUser(SanitizeNameMixin):
    """
    An object storing all user information.
    """

    def __init__(
        self,
        name,
        posix_uid=None,
        posix_gid=None,
        posix_home_path=None,
        home_group=None,
        shell=None,
        shadow=None,
        password=None,
        domain=None,
        pdc=None,
        primary_group_name=None,
        create_local_profile=False,
        windows_required_rights=None,
    ):
        """
        Convert user name to an OS valid value.
        """
        if posix_home_path is None:
            posix_home_path = '/tmp'

        if shell is None:
            shell = '/bin/sh'

        if shadow is None:
            shadow = '!'

        if posix_gid is None:
            posix_gid = posix_uid

        self._name = self.sanitizeName(name)
        self.uid = posix_uid
        self.gid = posix_gid
        self.posix_home_path = posix_home_path
        self.home_group = home_group
        self.shell = shell
        self.shadow = shadow
        self.password = password
        self.domain = domain
        self.pdc = pdc
        self.primary_group_name = primary_group_name

        self.windows_sid = None
        self.windows_create_local_profile = create_local_profile
        self.windows_required_rights = windows_required_rights
        self._windows_token = None

    @property
    def name(self):
        """
        Actual user name.
        """
        return self._name

    @property
    def token(self):
        """
        Windows token for user.
        """
        if os.name != 'nt':
            return None

        if not self._windows_token:
            self._windows_token = self._getToken()

        return self._windows_token

    @property
    def upn(self):
        """
        Returns User Principal Name: plain user name if no domain name defined
        or Active Directory compatible full domain user name.
        """
        if not self.domain:
            return self.name

        return f'{self.name}@{self.domain}'

    def _getToken(self):
        """
        Generate the Windows token for `user`.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
            username=self.upn,
            password=self.password,
        )

        if not result:
            message = (
                f'Failed to get a valid token for "{self.upn}" '
                f'with "{self.password}".'
            )
            raise AssertionError(message.encode('utf-8'))

        return token

    def _invalidateToken(self):
        """
        Invalidates cache for Windows token value.
        """
        self._windows_token = None


class TestGroup(SanitizeNameMixin):
    """
    An object storing all group information.
    """

    def __init__(self, name, posix_gid=None, members=None, pdc=None):
        """
        Convert name to an OS valid value.
        """
        if members is None:
            members = []

        self._name = self.sanitizeName(name)
        self.gid = posix_gid
        self.members = members
        self.pdc = pdc

    @property
    def name(self):
        """
        Actual group name.
        """
        return self._name


# Singleton member used to generate unique integers across whole tests.
# It starts with a different value to have different values between same
# test runs.
_unique_id = random.randint(0, 5000)


class ChevahCommonsFactory:
    """
    Generator of objects to help testing.
    """

    # Class member used for generating unique user/group id(s).
    _posix_id = random.randint(2000, 3000)

    @classmethod
    def getUniqueInteger(cls):
        """
        An integer unique for this session.
        """
        global _unique_id
        _unique_id += 1
        return _unique_id

    def bytes(self, size=8):
        """
        Returns a bytes array with random values that cannot be decoded
        as UTF-8.
        """
        result = bytearray(b'\xff')
        for _ in range(max(1, size - 1)):
            result.append(random.getrandbits(4))
        return bytes(result)

    def TCPPort(self, factory=None, address='', port=1234):
        """
        Return a Twisted TCP Port.
        """
        if factory is None:
            factory = Factory()

        return Port(port, factory, interface=address)

    def ascii(self):
        """
        Return a unique (per session) ASCII string.

        This is an Unicode with only ascii characters.
        """
        return 'ascii_StR' + six.text_type(self.number())

    def string(self, *args, **kwargs):
        """
        Shortcut for getUniqueString.
        """
        return self.getUniqueString(*args, **kwargs)

    def number(self, *args, **kwargs):
        """
        Shortcut for getUniqueInteger.
        """
        return self.getUniqueInteger(*args, **kwargs)

    def uuid1(self):
        """
        Generate a random UUID1 based on current machine.
        """
        return uuid.uuid1()

    def uuid4(self):
        """
        Generate a random UUID4.
        """
        return uuid.uuid4()

    @property
    def username(self):
        """
        The account under which this process is executed.
        """
        return six.text_type(os.environ['USER'])

    def getUniqueString(self, length=None):
        """
        A string unique for this session.
        """
        base = 'StR' + six.text_type(self.number())

        # The minimum length so that we don't truncate the unique string.
        min_length = len(base) + len(TEST_NAME_MARKER)
        extra_text = ''

        if length:
            # We add an extra 3 characters for safety.. since integers are not
            # padded.
            if min_length + 1 > length:
                raise AssertionError(
                    'Can not generate an unique string shorter than %d'
                    % (length),
                )
            extra_length = length - min_length
            extra_text = ''.join(
                random.choice(string.ascii_uppercase + string.digits)
                for ignore in range(extra_length)
            )

        return base + extra_text + TEST_NAME_MARKER

    def makeLocalTestFilesystem(self, avatar=None):
        if avatar is None:
            avatar = DefaultAvatar()
            avatar.home_folder_path = self.fs.temp_path
            avatar.root_folder_path = None

        return LocalTestFilesystem(avatar=avatar)

    _local_test_filesystem = None

    @property
    def local_test_filesystem(self):
        """Return the default local test filesystem."""
        if self.__class__._local_test_filesystem is None:
            self.__class__._local_test_filesystem = LocalTestFilesystem(
                avatar=DefaultAvatar(),
            )
        return self.__class__._local_test_filesystem

    @property
    def fs(self):
        """Shortcut for local_test_filesystem."""
        return self.local_test_filesystem

    def makeFilename(self, length=32, prefix='', suffix=''):
        """Return a random valid filename."""
        name = str(self.number()) + TEST_NAME_MARKER
        return prefix + name + ('a' * (length - len(name))) + suffix

    def FilesystemOsAvatar(self, user, home_folder_path=None):
        """
        Create an avatar to be used with the test filesystem.

        `user` is passed as a TestUser.
        """
        if home_folder_path is None:
            home_folder_path = user.posix_home_path

        return self.makeFilesystemOSAvatar(
            name=user.name,
            home_folder_path=home_folder_path,
            lock_in_home_folder=False,
            token=user.token,
        )

    def makeFilesystemOSAvatar(
        self,
        name=None,
        home_folder_path=None,
        root_folder_path=None,
        lock_in_home_folder=False,
        token=None,
    ):
        """
        Creates a valid FilesystemOSAvatar.
        """
        if name is None:
            name = self.username

        if home_folder_path is None:
            home_folder_path = self.fs.temp_path

        return FilesystemOSAvatar(
            name=name,
            home_folder_path=home_folder_path,
            root_folder_path=root_folder_path,
            lock_in_home_folder=lock_in_home_folder,
            token=token,
        )

    def makeFilesystemApplicationAvatar(
        self,
        name=None,
        home_folder_path=None,
        root_folder_path=None,
    ):
        """
        Creates a valid FilesystemApplicationAvatar.
        """
        if name is None:
            name = self.getUniqueString()

        if home_folder_path is None:
            home_folder_path = self.fs.temp_path

        # Application avatars are locked inside home folders.
        if root_folder_path is None:
            root_folder_path = home_folder_path

        return FilesystemApplicationAvatar(
            name=name,
            home_folder_path=home_folder_path,
            root_folder_path=root_folder_path,
        )

    @classmethod
    def posixID(cls):
        """
        Return a valid Posix ID.
        """
        cls._posix_id += 1
        return cls._posix_id

    def getTestUser(self, name):
        """
        Return an existing test user instance for user with `name`.
        Return `None` if user is undefined.
        """
        from chevah_compat.testing import TEST_USERS

        try:
            result = TEST_USERS[name]
        except KeyError:
            result = None

        return result

    def makeTestUser(
        self,
        name=None,
        password=None,
        posix_home_path=None,
        home_group=None,
    ):
        """
        Return an instance of TestUser with specified name and password.
        """
        if name is None:
            name = self.string()

        if password is None:
            password = self.string()

        if posix_home_path is None:
            if process_capabilities.os_name == 'solaris':
                posix_home_path = f'/export/home/{name}'
            elif process_capabilities.os_name == 'osx':
                posix_home_path = f'/Users/{name}'
            else:  # Linux and normal Unix
                posix_home_path = f'/home/{name}'

        return TestUser(
            name=name,
            password=password,
            posix_uid=self.posixID(),
            posix_home_path=posix_home_path,
            home_group=home_group,
        )


mk = ChevahCommonsFactory()
