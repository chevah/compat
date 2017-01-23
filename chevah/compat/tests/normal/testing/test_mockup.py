# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for the testing infrastructure.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future.types import newstr
import requests

from chevah.empirical.mockup import (
    ChevahCommonsFactory,
    ResponseDefinition,
    HTTPServerContext,
    )
from chevah.empirical import EmpiricalTestCase, mk


class TestHTTPServerContext(EmpiricalTestCase):
    """
    Tests for HTTPServerContext.
    """

    def getPage(
            self, location, method='GET', data=None,
            persistent=True, session=None,
            http_server=None,
            ):
        """
        Open a page using default mocked server.
        """
        if session is None:
            session = requests

        if http_server is None:
            http_server = self.httpd

        if method == 'POST':
            request_method = session.post
        else:
            request_method = session.get

        final_headers = {}
        if not persistent:
            final_headers['connection'] = 'close'

        return request_method(
            'http://%s:%d%s' % (http_server.ip, http_server.port, location),
            data=data,
            headers=final_headers,
            stream=False,
            )

    def test_HTTPServerContext_default(self):
        """
        Check HTTPServerContext.
        """
        response = ResponseDefinition(
            url='/test.html',
            response_content='test',
            method='GET',
            persistent=False,
            )

        with HTTPServerContext([response]) as self.httpd:
            self.assertIsNotNone(self.httpd.ip)
            self.assertIsNotNone(self.httpd.port)
            response = self.getPage('/test.html', persistent=False)
            self.assertEqual(u'test', response.text)

    def test_HTTPServerContext_close_without_connections(self):
        """
        Does not fail if just started without doing any connection.
        """
        with HTTPServerContext([]):
            pass

    def test_GET_no_response(self):
        """
        Return 404 when no response is configured.
        """
        with HTTPServerContext([]) as self.httpd:
            response = self.getPage('/test.html')

        self.assertEqual(404, response.status_code)

    def test_GET_not_found(self):
        """
        Return 404 when no configured response matches the requested URL.
        """
        response = ResponseDefinition(url='/other')
        with HTTPServerContext([response]) as self.httpd:
            response = self.getPage('/test.html')

        self.assertEqual(404, response.status_code)

    def test_GET_bad_method(self):
        """
        Return 404 when no configured response matches the requested method.
        """
        response = ResponseDefinition(method='POST', url='/url')
        with HTTPServerContext([response]) as self.httpd:
            response = self.getPage('/url')

        self.assertEqual(404, response.status_code)

    def test_GET_not_persistent(self):
        """
        Return 400 when request should be persistent but it is not.
        """
        response = ResponseDefinition(url='/url', persistent=True)
        with HTTPServerContext([response]) as self.httpd:
            response = self.getPage('/url', persistent=False)

        self.assertEqual(400, response.status_code)
        self.assertEqual(
            'Headers do not persist the connection', response.reason)

    def test_GET_persistent_ignore(self):
        """
        When set to None it will ignore the persistence check.
        """
        response = ResponseDefinition(url='/url', persistent=None)
        with HTTPServerContext([response]) as self.httpd:
            response = self.getPage('/url')

        self.assertEqual(200, response.status_code)

    def test_GET_persistent_good(self):
        """
        Will pass if connections are made using same connection,
        ie they are persisted.
        """
        response = ResponseDefinition(
            method='GET',
            url='/url',
            response_content='good',
            persistent=True,
            )

        session = requests.Session()

        with HTTPServerContext([response]) as self.httpd:
            response = self.getPage('/url', session=session)

            self.assertEqual(200, response.status_code)

            response = self.getPage('/url', session=session)

            self.assertEqual(200, response.status_code)
            self.assertEqual('good', response.content)

    def test_GET_persistent_not_reused(self):
        """
        Will fail if connections are not made using same remote connection.
        """
        response = ResponseDefinition(
            method='GET',
            url='/url',
            response_content='good',
            persistent=True,
            )

        with HTTPServerContext([response]) as self.httpd:
            response = self.getPage('/url')

            self.assertEqual(200, response.status_code)

            response = self.getPage('/url')

            self.assertEqual(400, response.status_code)
            self.assertEqual(
                'Persistent connection not reused', response.reason)

    def test_do_POST_good(self):
        """
        A request of type POST is matched when request content also match.
        """
        response = ResponseDefinition(
            method='POST',
            url='/url',
            request='request-body',
            persistent=False,
            response_code=242,
            response_message='All good.',
            response_content='content',
            )
        with HTTPServerContext([response]) as self.httpd:
            response = self.getPage(
                '/url', method='POST', data='request-body', persistent=False)

            self.assertEqual(242, response.status_code)
            # Read content before closing the server.
            self.assertEqual(u'content', response.text)

    def test_do_POST_invalid_content(self):
        """
        A request of type POST is not matched when request content differs.
        """
        response = ResponseDefinition(
            method='POST',
            url='/url',
            request='request-body',
            persistent=False,
            )
        with HTTPServerContext([response]) as self.httpd:
            response = self.getPage('/url', method='POST', data='other-body')

        self.assertEqual(404, response.status_code)

    def test_nested_calls(self):
        """
        Multiple contexts can be nested.
        """
        first_response = ResponseDefinition(
            url='/url',
            persistent=True,
            response_content='first-level'
            )
        nested_response = ResponseDefinition(
            url='/url',
            persistent=False,
            response_content='nested-level'
            )

        with HTTPServerContext([first_response]) as self.httpd:
            with HTTPServerContext([nested_response]) as nested_httpd:
                result = self.getPage(
                    '/url', persistent=False, http_server=nested_httpd)

                self.assertEqual(200, result.status_code)
                self.assertEqual('nested-level', result.content)

            result = self.getPage('/url', persistent=True)

        self.assertEqual(200, result.status_code)
        self.assertEqual('first-level', result.content)

    def test_updateResponseContent(self):
        """
        The response content can be updated after initialization.
        """
        response = ResponseDefinition(
            url='/url',
            persistent=False,
            response_content='first-content-of-different-length'
            )
        with HTTPServerContext([response]) as self.httpd:
            response.updateReponseContent('updated-content')

            result = self.getPage('/url', persistent=False)

        self.assertEqual(200, result.status_code)
        self.assertEqual('updated-content', result.content)
        self.assertEqual('15', result.headers['content-length'])


class TestFactory(EmpiricalTestCase):
    """
    Test for test objects factory.
    """

    def test_string(self):
        """
        It will return different values at each call.

        Value is Unicode.
        """
        self.assertNotEqual(
            mk.string(),
            mk.string(),
            )
        self.assertIsInstance(newstr, mk.string())

    def test_number(self):
        """
        It will return different values at each call.
        """
        self.assertNotEqual(
            mk.number(),
            mk.number(),
            )

    def test_ascii(self):
        """
        It will return different values at each call.

        Value is str.
        """
        self.assertNotEqual(
            mk.ascii(),
            mk.ascii(),
            )
        self.assertIsInstance(str, mk.ascii())

    def test_bytes(self):
        """
        It will return different values with each call.
        """
        self.assertNotEqual(mk.bytes(), mk.bytes())
        self.assertIsInstance(bytearray, mk.bytes())

    def test_bytes_string_conversion(self):
        """
        Conversion to unicode will fail for ASCII/UTF-8/UTF-16.
        """
        value = mk.bytes(size=32)

        with self.assertRaises(UnicodeDecodeError):
            value.decode()

        with self.assertRaises(UnicodeDecodeError):
            value.decode(encoding='ascii')

        with self.assertRaises(UnicodeDecodeError):
            value.decode(encoding='utf-8')

        if self.os_name != 'aix':
            # FIXME:3816:
            # Fix this on AIX.
            with self.assertRaises(UnicodeDecodeError):
                value.decode(encoding='utf-16')

    class OneFactory(ChevahCommonsFactory):
        """
        Minimal class to help with testing
        """

    class OtherFactory(ChevahCommonsFactory):
        """
        Minimal class to help with testing
        """

    def test_getUniqueInteger(self):
        """
        Integer is unique between various classes implementing the factory.
        """
        one = self.OneFactory()
        other = self.OtherFactory()

        self.assertNotEqual(
            one.getUniqueInteger(),
            other.getUniqueInteger(),
            )
