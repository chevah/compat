# Copyright (c) 2017 Adi Roiban.
# See LICENSE for details.
"""
Assertion helpers for compat testing.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from six import next, text_type
from contextlib import contextmanager
import collections
import time

try:
    from twisted.python.failure import Failure
except ImportError:
    # Twisted support is optional.
    pass

try:
    from zope.interface.verify import verifyObject
except ImportError:
    # Zope support is optional.
    pass

from chevah.compat.exceptions import CompatError


class Contains(object):
    """
    Marker class used in tests when something needs to contain a value.
    """
    def __init__(self, value):
        self.value = value


class AssertionMixin(object):
    """
    Mixin to be combined with a test case for providing additional assertions.
    """

    Contains = Contains

    @classmethod
    def assertTempIsClean(cls):
        """
        Raise an error if the temporary folder contains any testing
        specific files for folders.
        """
        members = cls.cleanTemporaryFolder()
        if members:
            message = u'Temporary folder is not clean. %s' % (
                u', '.join(members))
            raise AssertionError(message.encode('utf-8'))

    @classmethod
    def assertWorkingFolderIsClean(cls):
        """
        Raise an error if the current working folder contains any testing
        specific files for folders.
        """
        members = cls.cleanWorkingFolder()
        if members:
            message = u'Working folder is not clean. %s' % (
                u', '.join(members))
            raise AssertionError(message.encode('utf-8'))

    def assertEqual(self, first, second, msg=None):
        '''Extra checks for assert equal.'''
        try:
            super(AssertionMixin, self).assertEqual(first, second, msg)
        except AssertionError as error:  # noqa:cover
            message = error.message
            if isinstance(message, text_type):
                message = message.encode('utf-8')
            raise AssertionError(message)

        if (
            isinstance(first, text_type) and
            not isinstance(second, text_type)
                ):  # noqa:cover
            if not msg:
                msg = u'Type of "%s" is unicode while for "%s" is str.' % (
                    first, second)
            raise AssertionError(msg.encode('utf-8'))

        if (
            not isinstance(first, text_type) and
            isinstance(second, text_type)
                ):  # noqa:cover
            if not msg:
                msg = u'Type of "%s" is str while for "%s" is unicode.' % (
                    first, second)
            raise AssertionError(msg.encode('utf-8'))

    def assertIteratorEqual(self, expected, actual):
        """
        Check that once fully iterated the `actual` iterator will return the
        `expected` list.
        """
        actual_list = []
        while True:
            try:
                actual_list.append(next(actual))
            except TypeError:
                raise AssertionError('Value is not iterable.')
            except StopIteration:
                break
        self.assertEqual(expected, actual_list)

    def assertCompatError(self, expected_id, actual_error):
        """
        Raise an error if `actual_error` is not a `CompatError` instance.

        Raise an error if `expected_id` does not match event_id of
        `actual_error`.
        """
        if not isinstance(actual_error, CompatError):
            values = (actual_error, type(actual_error))
            message = u'Error %s not CompatError but %s' % values
            raise AssertionError(message.encode('utf-8'))

        actual_id = getattr(actual_error, 'event_id', None)
        if expected_id != actual_id:
            values = (
                actual_error, text_type(expected_id), text_type(actual_id))
            message = u'Error id for %s is not %s, but %s.' % values
            raise AssertionError(message.encode('utf-8'))

    def assertIsFalse(self, value):
        """
        Raise an exception if value is not 'False'.
        """
        if value is not False:
            raise AssertionError('%s is not False.' % text_type(value))

    def assertIsTrue(self, value):
        """
        Raise an exception if value is not 'True'.
        """
        if value is not True:
            raise AssertionError('%s is not True.' % text_type(value))

    def assertFailureType(self, failure_class, failure_or_deferred):
        '''Raise assertion error if failure is not of required type.'''
        if isinstance(failure_or_deferred, Failure):
            failure = failure_or_deferred
        else:
            self.assertIsFailure(failure_or_deferred)
            failure = failure_or_deferred.result

        if failure.type is not failure_class:  # noqa:cover
            message = u'Failure %s is not of type %s' % (
                text_type(failure), failure_class)
            raise AssertionError(message.encode('utf-8'))

    def _checkData(self, kind, kind_id, expected_data, current_data):
        """
        Helper for sharing same code between various data checkers.
        """
        for key, value in expected_data.items():
            try:
                current_value = current_data[key]

                if isinstance(value, Contains):
                    if value.value not in current_value:
                        message = (
                            u'%s %s, for data "%s" does not contains "%s", '
                            u'but is "%s"') % (
                            kind, text_type(kind_id), key, value.value,
                            current_value)
                        raise AssertionError(message.encode('utf-8'))
                else:
                    if value != current_value:
                        message = (
                            u'%s %s, for data "%s" is not "%s", but "%s"') % (
                            kind,
                            text_type(kind_id),
                            key,
                            repr(value),
                            repr(current_value),
                            )
                        raise AssertionError(message.encode('utf-8'))
            except KeyError:  # noqa:cover
                values = (
                    kind, text_type(kind_id), repr(key), repr(current_data))
                message = u'%s %s, has no data "%s". Data is:\n%s' % values
                raise AssertionError(message.encode('utf-8'))

    def assertIsEmpty(self, target):
        """
        Raise AssertionError if target is not empty.
        """
        if isinstance(target, collections.Iterable):
            iterator = iter(target)
            try:
                next(iterator)
            except StopIteration:
                pass
            else:
                message = u'Iterable is not empty.\n%s.' % (
                    repr(target).decode('utf-8'),)
                raise AssertionError(message.encode('utf-8'))
            return

        if len(target) != 0:
            message = u'Value is not empty.\n%s.' % (target,)
            raise AssertionError(message.encode('utf-8'))

    def assertIsNotEmpty(self, target):
        """
        Raise AssertionError if target is empty.
        """
        if isinstance(target, collections.Iterable):
            try:
                self.assertIsEmpty(target)
            except AssertionError:
                pass
            else:
                message = u'Iterable is empty.\n%s.' % target
                raise AssertionError(message.encode('utf-8'))
            return

        if len(target) == 0:
            raise AssertionError('Value is empty.\n%s.' % (target))

    def assertContains(self, token, source):
        """
        Raise AssertionError if source does not contain `token`.
        """
        if token not in source:
            message = u'%s does not contains %s.' % (
                repr(source), repr(token))
            raise AssertionError(message.encode('utf-8'))

    def assertNotContains(self, token, source):
        """
        Raise AssertionError if source does contain `token`.
        """
        if token in source:
            message = u'%s contains %s.' % (repr(source), repr(token))
            raise AssertionError(message.encode('utf-8'))

    def assertTextContains(self, pattern, source):
        """
        Raise AssertionError if pattern is not found in source.
        """
        if pattern not in pattern:
            message = u'%s not contained in\n%s.' % (
                repr(pattern), repr(source))
            raise AssertionError(message.encode('utf-8'))

    def assertStartsWith(self, start, source):
        """
        Raise AssertionError if `source` does not starts with `start`.
        """
        if not source.startswith(start):
            message = u'%s does not starts with %s' % (
                repr(source), repr(start))
            raise AssertionError(message.encode('utf-8'))

    def assertEndsWith(self, end, source):
        """
        Raise AssertionError if `source` does not ends with `end`.
        """
        if not source.endswith(end):
            message = u'%s does not end with %s' % (repr(source), repr(end))
            raise AssertionError(message.encode('utf-8'))

    def assertProvides(self, interface, obj):
        self.assertTrue(
            interface.providedBy(obj),
            'Object %s does not provided interface %s.' % (obj, interface))
        verifyObject(interface, obj)

    def assertNotProvides(self, interface, obj):
        self.assertFalse(
            interface.providedBy(obj),
            'Object %s does not provided interface %s.' % (obj, interface))

    def assertImplements(self, interface, klass):
        self.assertTrue(
            interface.implementedBy(klass),
            u'Class %s does not implements interface %s.' % (
                klass, interface))

    @contextmanager
    def assertExecutionTime(self, seconds):
        """
        Check that code executes in less than `seconds` as a context manager.
        """
        start = time.time()
        yield
        duration = time.time() - start
        self.assertLess(
            duration, seconds, 'Took %s. Expecting less than %s' % (
                duration, seconds,))
