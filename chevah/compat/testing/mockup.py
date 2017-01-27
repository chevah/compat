# -*- coding: utf-8 -*-
"""
Module containing helpers for testing the Chevah project.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import str
from builtins import range
from builtins import object
from future.utils import native

from select import error as SelectError
from threading import Thread
import codecs
import http.server
import errno
import hashlib
import http.client
import os
import random
import socket
import string
import sys
import threading
import uuid

from unidecode import unidecode

try:
    from twisted.internet import address
    from twisted.internet.protocol import Factory
    from twisted.internet.tcp import Port
except ImportError:  # pragma: no cover
    # Twisted support is optional.
    pass

from chevah.compat import DefaultAvatar, process_capabilities, system_users
from chevah.compat.avatar import (
    FilesystemApplicationAvatar,
    FilesystemOSAvatar,
    )
from chevah.compat.testing.filesystem import LocalTestFilesystem
from chevah.compat.testing.constants import (
    TEST_NAME_MARKER,
    )


class _StoppableHTTPServer(http.server.HTTPServer):
    """
    Single connection HTTP server designed to respond to HTTP requests in
    functional tests.
    """
    server_version = 'ChevahTesting/0.1'
    stopped = False
    # Current connection served by the server.
    active_connection = None

    def serve_forever(self):
        """
        Handle one request at a time until stopped.
        """
        self.stopped = False
        self.active_connection = None
        while not self.stopped:
            try:
                self.handle_request()
            except SelectError as e:
                # See Python http://bugs.python.org/issue7978
                if e.args[0] == errno.EINTR:
                    continue
                raise


class _ThreadedHTTPServer(Thread):
    """
    HTTP Server that runs in a thread.

    This is actual a threaded wrapper around an HTTP server.

    Only use it for testing together with HTTPServerContext.
    """
    TIMEOUT = 1

    def __init__(
            self, responses=None, ip='127.0.0.1', port=0, debug=False,
            cond=None):
        Thread.__init__(self)
        self.ready = False
        self.cond = cond
        self._ip = ip
        self._port = port

    def run(self):
        self.cond.acquire()
        timeout = 0
        self.httpd = None
        while self.httpd is None:
            try:
                self.httpd = _StoppableHTTPServer(
                    (self._ip, self._port), _DefinedRequestHandler)
            except Exception as e:
                # I have no idea why this code works.
                # It is a copy paste from:
                # http://www.ianlewis.org/en/testing-using-mocked-server
                import errno
                import time
                if (isinstance(e, socket.error) and
                        errno.errorcode[e.args[0]] == 'EADDRINUSE' and
                        timeout < self.TIMEOUT):
                    timeout += 1
                    time.sleep(1)
                else:
                    self.cond.notifyAll()
                    self.cond.release()
                    self.ready = True
                    raise e

        self.ready = True
        if self.cond:
            self.cond.notifyAll()
            self.cond.release()
        # Start the actual HTTP server.
        self.httpd.serve_forever()


class HTTPServerContext(object):
    """
    A context manager which runs a HTTP server for testing simple
    HTTP requests.

    After the server is started the ip and port are available in the
    context management instance.

    response = ResponseDefinition(url='/hello.html', response_content='Hello!)
    with HTTPServerContext([response]) as httpd:
        print 'Listening at %s:%d' % (httpd.id, httpd.port)
        self.assertEqual('Hello!', your_get())

    responses = ResponseDefinition(
        url='/hello.php', request='user=John',
        response_content='Hello John!, response_code=202)
    with HTTPServerContext([response]) as httpd:
        self.assertEqual(
            'Hello John!',
            get_you_post(url='hello.php', data='user=John'))
    """

    def __init__(
            self, responses=None, ip='127.0.0.1', port=0,
            version='HTTP/1.1', debug=False):
        """
        Initialize a new HTTPServerContext.

         * ip - IP to listen. Leave empty to listen to any interface.
         * port - Port to listen. Leave 0 to pick a random port.
         * server_version - HTTP version used by server.
         * responses - A list of ResponseDefinition defining the behavior of
                        this server.
        """
        self._previous_valid_responses = _DefinedRequestHandler.valid_responses
        self._previous_first_client = _DefinedRequestHandler.first_client

        # Since we can not pass an instance of _DefinedRequestHandler
        # we do on the fly patching here.
        _DefinedRequestHandler.debug = debug
        if responses is None:
            _DefinedRequestHandler.valid_responses = []
        else:
            _DefinedRequestHandler.valid_responses = responses

        _DefinedRequestHandler.protocol_version = version
        self.cond = threading.Condition()
        self.server = _ThreadedHTTPServer(cond=self.cond, ip=ip, port=port)

    def __enter__(self):
        self.cond.acquire()
        self.server.start()

        # Wait until the server is ready.
        while not self.server.ready:
            self.cond.wait()
        self.cond.release()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        # _DefinedRequestHandler initialization is outside of control so
        # we share state as class members. To free memory we need to clean it.
        _DefinedRequestHandler.cleanGlobals()

        _DefinedRequestHandler.valid_responses = self._previous_valid_responses
        _DefinedRequestHandler.first_client = self._previous_first_client

        self.stopServer()
        self.server.join(1)
        if self.server.isAlive():
            raise AssertionError('Server still running')

        return False

    @property
    def port(self):
        return self.server.httpd.server_address[1]

    @property
    def ip(self):
        return self.server.httpd.server_address[0]

    def stopServer(self):
        connection = self.server.httpd.active_connection
        if connection and connection.rfile._sock:
            # Stop waiting for data from persistent connection.
            self.server.httpd.stopped = True
            sock = connection.rfile._sock
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except socket.error:
                # Ignore socket errors at shutdown as the connection
                # might be already closed.
                pass
        else:
            # Stop waiting for data from new connection.
            # This is done by sending a special QUIT request without
            # waiting for data.
            conn = http.client.HTTPConnection("%s:%d" % (self.ip, self.port))
            conn.request("QUIT", "/")
            conn.getresponse()
        self.server.httpd.server_close()


class _DefinedRequestHandler(http.server.BaseHTTPRequestHandler, object):
    """
    A request handler which act based on pre-defined responses.

    This should only be used for test together with HTTPServerContext.
    """

    valid_responses = []

    debug = False
    # Keep a record of first client which connects to the request
    # series to have a better check for persisted connections.
    first_client = None

    def __init__(self, request, client_address, server):
        if self.debug:
            print('New connection %s.' % (client_address,))
        # Register current connection on server.
        server.active_connection = self
        try:
            super(_DefinedRequestHandler, self).__init__(
                request, client_address, server)
        except socket.error:
            pass
        server.active_connection = None

    @classmethod
    def cleanGlobals(cls):
        """
        Clean all class methods used to share info between different requests.
        """
        cls.valid_responses = None
        cls.first_client = None

    def log_message(self, *args):
        pass

    def do_QUIT(self):
        """
        Called by HTTPServerContext to trigger server stop.
        """
        self.server.stopped = True
        self._debug('QUIT')
        self.send_response(200)
        self.end_headers()
        # Force closing the connection.
        self.close_connection = 1

    def do_GET(self):
        self._handleRequest()

    def do_POST(self):
        self._handleRequest()

    def _handleRequest(self):
        """
        Check if we can handle the request and send response.
        """
        if not self.first_client:
            # Looks like this is the first request so we save the client
            # address to compare it later.
            self.__class__.first_client = self.client_address

        response = self._matchResponse()
        if response:
            self._debug(response)
            self._sendResponse(response)
            self._debug('Close-connection: %s' % (self.close_connection,))
            return

        self.send_error(404)

    def _matchResponse(self):
        """
        Return the ResponseDefinition for the current request.
        """
        for response in self.__class__.valid_responses:
            if self.path != response.url or self.command != response.method:
                self._debug()
                continue

            # For POST request we read content.
            if self.command == 'POST':
                length = int(self.headers.getheader('content-length'))
                content = self.rfile.read(length)
                if content != response.request:
                    self._debug(content)
                    continue

            # We have a match.
            return response

        return None

    def _debug(self, message=''):
        """
        Print to stdout a debug message.
        """
        if not self.debug:
            return
        print('\nGot %s:%s - %s\n' % (
            self.command, self.path, message))

    def _sendResponse(self, response):
        """
        Send response to client.
        """
        connection_header = self.headers.getheader('connection')
        if connection_header:
            connection_header = connection_header.lower()

        if self.protocol_version == 'HTTP/1.1':
            # For HTTP/1.1 connections are persistent by default.
            if not connection_header:
                connection_header = 'keep-alive'
        else:
            # For HTTP/1.0 connections are not persistent by default.
            if not connection_header:
                connection_header = 'close'

        if response.persistent is None:
            # Ignore persistent flag.
            pass
        elif response.persistent:
            if connection_header == 'close':
                self.send_error(400, 'Headers do not persist the connection')

            if self.first_client != self.client_address:
                self.send_error(400, 'Persistent connection not reused')
        else:
            if connection_header == 'keep-alive':
                self.send_error(400, 'Connection was persistent')

        self.send_response(
            response.response_code, response.response_message)
        self.send_header("Content-Type", response.content_type)

        if response.response_length:
            self.send_header("Content-Length", response.response_length)

        self.end_headers()
        self.wfile.write(response.test_response_content)

        if not response.response_persistent:
            # Force closing the connection as requested
            # by response.
            self.close_connection = 1


class ResponseDefinition(object):
    """
    A class encapsulating the required data for configuring a response
    generated by the HTTPServerContext.

    It contains the following data:
        * url - url that will trigger this response
        * request - request that will trigger the response once the url is
                    matched
        * response_content - content of the response
        * response_code - HTTP code of the response
        * response_message - Message sent together with HTTP code.
        * content_type - Content type of the HTTP response
        * response_length - Length of the response body content.
          `None` to calculate automatically the length.
          `` (empty string) to ignore content-length header.
        * persistent: whether the request should persist the connection.
          Set to None to ignore persistent checking.
    """

    def __init__(
        self, url='', request='', method='GET',
        response_content='', response_code=200, response_message=None,
        content_type='text/html', response_length=None,
        persistent=True, response_persistent=None,
            ):
        self.url = url
        self.method = method
        self.request = request
        if not isinstance(response_content, bytes):
            response_content = codecs.encode(response_content, 'utf-8')
        self.test_response_content = response_content
        self.response_code = response_code
        self.response_message = response_message
        self.content_type = content_type
        if response_length is None:
            response_length = len(self.test_response_content)
        self.response_length = str(response_length)
        self.persistent = persistent
        if response_persistent is None:
            response_persistent = persistent

        self.response_persistent = response_persistent

    def __repr__(self):
        return 'ResponseDefinition:%s:%s:%s %s:pers-%s' % (
            self.url,
            self.method,
            self.response_code, self.response_message,
            self.persistent,
            )

    def updateResponseContent(self, content):
        """
        Will update the content returned to the server.
        """
        self.test_response_content = content
        response_length = len(content)
        self.response_length = str(response_length)


# FIXME:2106:
# Get rid of global functions and replace with OS specialized TestUSer
# instances: TestUserAIX, TestUserWindows, TestUserUnix, etc.
def _sanitize_name_legacy_unix(candidate):
    """
    Return valid user/group name for old Unix (AIX/HPUX) from `candidate`.

    By default password is limited to 8 characters without spaces.
    """
    return str(unidecode(candidate)).replace(' ', '_')[:8]


def _sanitize_name_windows(candidate):
    """
    Return valid user/group name for Windows OSs from `candidate.
    """
    # FIXME:927:
    # On Windows, we can't delete home folders with unicode names.
    return str(unidecode(candidate))


class TestUser(object):
    """
    An object storing all user information.
    """

    @classmethod
    def sanitizeName(cls, name):
        """
        Return name sanitized for current OS.
        """
        os_name = process_capabilities.os_name
        if os_name in ['aix', 'hpux']:
            return _sanitize_name_legacy_unix(name)
        elif os_name == 'windows':
            return _sanitize_name_windows(name)

        return name

    def __init__(
        self, name, posix_uid=None, posix_gid=None, posix_home_path=None,
        home_group=None, shell=None, shadow=None, password=None,
        domain=None, pdc=None, primary_group_name=None,
        create_local_profile=False, windows_required_rights=None,
            ):
        """
        Convert user name to an OS valid value.
        """
        if posix_home_path is None:
            posix_home_path = u'/tmp'

        if shell is None:
            shell = u'/bin/sh'

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

        return u'%s@%s' % (self.name, self.domain)

    def _getToken(self):
        """
        Generate the Windows token for `user`.
        """
        result, token = system_users.authenticateWithUsernameAndPassword(
            username=self.upn, password=self.password)

        if not result:
            message = u'Failed to get a valid token for "%s" with "%s".' % (
                self.upn, self.password)
            raise AssertionError(message.encode('utf-8'))

        return token

    def _invalidateToken(self):
        """
        Invalidates cache for Windows token value.
        """
        self._windows_token = None


class TestGroup(object):
    """
    An object storing all group information.
    """

    @classmethod
    def sanitizeName(cls, group):
        """
        Return name sanitized for current OS.
        """
        if sys.platform.startswith('aix'):
            return _sanitize_name_legacy_unix(group)
        elif sys.platform.startswith('win'):
            return _sanitize_name_windows(group)

        return group

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


class ChevahCommonsFactory(object):
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

    def ascii(self):
        """
        Return a unique (per session) ASCII string.
        """
        return native(
            ('ascii_str' + str(self.getUniqueInteger()).encode('utf-8')))

    def bytes(self, size=8):
        """
        Returns a bytes array with random values that cannot be decoded
        as UTF-8.
        """
        result = bytearray(b'\xff')
        for _ in range(max(1, size - 1)):
            result.append(random.getrandbits(4))
        return result

    def TCPPort(self, factory=None, address='', port=1234):
        """
        Return a Twisted TCP Port.
        """
        if factory is None:
            factory = Factory()

        return Port(port, factory, interface=address)

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
        return str(os.environ['USER'])

    def md5(self, content):
        """
        Return MD5 digest for `content`.

        Content must by byte string.
        """
        md5_sum = hashlib.md5()
        md5_sum.update(content)
        return md5_sum.digest()

    def getUniqueString(self, length=None):
        """
        A string unique for this session.
        """
        base = u'str' + str(self.getUniqueInteger())

        # The minimum length so that we don't truncate the unique string.
        min_length = len(base) + len(TEST_NAME_MARKER)
        extra_text = ''

        if length:
            # We add an extra 3 characters for safety.. since integers are not
            # padded.
            if min_length + 1 > length:
                raise AssertionError(
                    "Can not generate an unique string shorter than %d" % (
                        length))
            else:
                extra_length = length - min_length
                extra_text = ''.join(
                    random.choice(string.ascii_uppercase + string.digits)
                    for ignore in range(extra_length)
                    )

        return native(base + extra_text + TEST_NAME_MARKER)

    def makeLocalTestFilesystem(self, avatar=None):
        if avatar is None:
            avatar = DefaultAvatar()
            avatar.home_folder_path = self.fs.temp_path
            avatar.root_folder_path = None

        return LocalTestFilesystem(avatar=avatar)

    _local_test_filesystem = None

    @property
    def local_test_filesystem(self):
        '''Return the default local test filesystem.'''
        if self.__class__._local_test_filesystem is None:
            self.__class__._local_test_filesystem = (
                LocalTestFilesystem(avatar=DefaultAvatar()))
        return self.__class__._local_test_filesystem

    @property
    def fs(self):
        '''Shortcut for local_test_filesystem.'''
        return self.local_test_filesystem

    def makeFilename(self, length=32, prefix=u'', suffix=u''):
        '''Return a random valid filename.'''
        name = str(self.getUniqueInteger()) + TEST_NAME_MARKER
        return native(prefix + name + ('a' * (length - len(name))) + suffix)

    def makeIPv4Address(self, host='localhost', port=None, protocol='TCP'):
        """
        Creates an IPv4 address.
        """
        if port is None:
            port = random.randrange(20000, 30000)

        ipv4 = address.IPv4Address(protocol, host, port)
        return ipv4

    def makeFilesystemOSAvatar(
        self, name=None, home_folder_path=None, root_folder_path=None,
        lock_in_home_folder=False, token=None,
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
            self, name=None, home_folder_path=None, root_folder_path=None):
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
        from chevah.compat.testing import TEST_USERS
        try:
            result = TEST_USERS[name]
        except KeyError:
            result = None

        return result

    def makeTestUser(self, name=None, password=None, posix_home_path=None,
                     home_group=None
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
                posix_home_path = u'/export/home/%s' % name
            elif process_capabilities.os_name == 'osx':
                posix_home_path = u'/Users/%s' % name
            else:  # Linux and normal Unix
                posix_home_path = u'/home/%s' % name

        return TestUser(
            name=name,
            password=password,
            posix_uid=self.posixID(),
            posix_home_path=posix_home_path,
            home_group=home_group,
            )


mk = ChevahCommonsFactory()
