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

from select import error as SelectError
from threading import Thread
import http.server
import errno
import hashlib
import http.client
import os
import random
import socket
import string
import threading
import uuid

from OpenSSL import SSL, crypto

try:
    from twisted.internet import address, defer
    from twisted.internet.protocol import Factory
    from twisted.internet.tcp import Port
except ImportError:
    # Twisted support is optional.
    pass

from chevah.compat import DefaultAvatar
from chevah.empirical.filesystem import LocalTestFilesystem
from chevah.empirical.constants import (
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
        self.test_response_content = response_content
        self.response_code = response_code
        self.response_message = response_message
        self.content_type = content_type
        if response_length is None:
            response_length = len(response_content)
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

    def updateReponseContent(self, content):
        """
        Will update the content returned to the server.
        """
        self.test_response_content = content
        response_length = len(content)
        self.response_length = str(response_length)


class TestSSLContextFactory(object):
    '''An SSLContextFactory used in tests.'''

    def __init__(self, factory, method=None, cipher_list=None,
                 certificate_path=None, key_path=None):
        self.method = method
        self.cipher_list = cipher_list
        self.certificate_path = certificate_path
        self.key_path = key_path
        self._context = None

    def getContext(self):
        if self._context is None:
            self._context = factory.makeSSLContext(
                method=self.method,
                cipher_list=self.cipher_list,
                certificate_path=self.certificate_path,
                key_path=self.key_path,
                )
        return self._context


# Singleton member used to generate unique integers across whole tests.
# It starts with a different value to have different values between same
# test runs.
_unique_id = random.randint(0, 5000)


class ChevahCommonsFactory(object):
    """
    Generator of objects to help testing.
    """

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
        return ('ascii_str' + str(self.getUniqueInteger())).encode('ascii')

    def bytes(self, size=8):
        """
        Returns a bytes array with random values that cannot be decoded
        as UTF-8.
        """
        result = bytearray(b'\xff\xd8\x00\x01')
        for _ in range(max(4, size - 4)):
            result.append(random.getrandbits(8))
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
        return prefix + name + ('a' * (length - len(name))) + suffix

    def makeIPv4Address(self, host='localhost', port=None, protocol='TCP'):
        """
        Creates an IPv4 address.
        """
        if port is None:
            port = random.randrange(20000, 30000)

        ipv4 = address.IPv4Address(protocol, host, port)
        return ipv4

    def makeSSLContext(
        self, method=None, cipher_list=None,
        certificate_path=None, key_path=None,
            ):
        '''Create an SSL context.'''
        if method is None:
            method = SSL.SSLv23_METHOD

        if key_path is None:
            key_path = certificate_path

        ssl_context = SSL.Context(method)

        if certificate_path:
            ssl_context.use_certificate_file(certificate_path)
        if key_path:
            ssl_context.use_privatekey_file(key_path)

        if cipher_list:
            ssl_context.set_cipher_list(cipher_list)

        return ssl_context

    def makeSSLContextFactory(
        self, method=None, cipher_list=None,
        certificate_path=None, key_path=None,
            ):
        '''Return an instance of SSLContextFactory.'''
        return TestSSLContextFactory(
            self, method=method, cipher_list=cipher_list,
            certificate_path=certificate_path, key_path=key_path)

    def makeSSLCertificate(self, path):
        '''Return an SSL instance loaded from path.'''
        certificate = None
        cert_file = open(path, 'r')
        try:
            certificate = crypto.load_certificate(
                crypto.FILETYPE_PEM, cert_file.read())
        finally:
            cert_file.close()
        return certificate

    def makeDeferredSucceed(self, data=None):
        """
        Creates a deferred for which already succeeded.
        """
        return defer.succeed(data)

    def makeDeferredFail(self, failure=None):
        """
        Creates a deferred which already failed.
        """
        return defer.fail(failure)


factory = ChevahCommonsFactory()
