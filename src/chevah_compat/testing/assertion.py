# Copyright (c) 2017 Adi Roiban.
# See LICENSE for details.
"""
Assertion helpers for compat testing.
"""

import collections
import time
from contextlib import contextmanager

from six import text_type

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

from chevah_compat.exceptions import CompatError


class Contains:
    """
    Marker class used in tests when something needs to contain a value.
    """

    def __init__(self, *value):
        self._values = value

    def __eq__(self, other):
        for value in self._values:
            if value not in other:
                return False
        return None

    def __hash__(self):  # pragma: no cover
        return hash(self._value[0])


class AssertionMixin:
    """
    Mixin to be combined with a test case for providing additional assertions.

    The assertions from here should not overwrite anything.
    """

    def assertItemsEqual(self, first, second, message=None):
        return self.assertCountEqual(first, second, message)

    @classmethod
    def assertTempIsClean(cls):
        """
        Raise an error if the temporary folder contains any testing
        specific files for folders.
        """
        members = cls.cleanTemporaryFolder()
        if members:
            message = 'Temporary folder is not clean. {}'.format(
                ', '.join(members)
            )
            raise AssertionError(message)

    @classmethod
    def assertWorkingFolderIsClean(cls):
        """
        Raise an error if the current working folder contains any testing
        specific files for folders.
        """
        members = cls.cleanWorkingFolder()
        if members:
            message = 'Working folder is not clean. {}'.format(
                ', '.join(members)
            )
            raise AssertionError(message)

    def assertIteratorItemsEqual(self, expected, actual):
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
        self.assertItemsEqual(expected, actual_list)

    def assertCompatError(self, expected_id, actual_error):
        """
        Raise an error if `actual_error` is not a `CompatError` instance.

        Raise an error if `expected_id` does not match event_id of
        `actual_error`.
        """
        if not isinstance(actual_error, CompatError):
            values = (actual_error, type(actual_error))
            message = 'Error {} not CompatError but {}'.format(*values)
            raise AssertionError(message)  # noqa: TRY004

        actual_id = getattr(actual_error, 'event_id', None)
        if expected_id != actual_id:
            values = (
                actual_error,
                text_type(expected_id),
                text_type(actual_id),
            )
            message = 'Error id for {} is not {}, but {}.'.format(*values)
            raise AssertionError(message)

    def assertIsFalse(self, value):
        """
        Raise an exception if value is not 'False'.
        """
        if value is not False:
            raise AssertionError(f'{text_type(value)} is not False.')

    def assertIsTrue(self, value):
        """
        Raise an exception if value is not 'True'.
        """
        if value is not True:
            raise AssertionError(f'{text_type(value)} is not True.')

    def assertFailureType(self, failure_class, failure_or_deferred):
        """Raise assertion error if failure is not of required type."""
        if isinstance(failure_or_deferred, Failure):
            failure = failure_or_deferred
        else:
            self.assertIsFailure(failure_or_deferred)
            failure = failure_or_deferred.result

        if failure.type is not failure_class:  # pragma: no cover
            message = (
                f'Failure {text_type(failure)} is not of type {failure_class}'
            )
            raise AssertionError(message)

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
                message = f'Iterable is not empty.\n{target!r}.'
                raise AssertionError(message)
            return

        if len(target) != 0:
            message = f'Value is not empty.\n{target}.'
            raise AssertionError(message)

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
                message = f'Iterable is empty.\n{target}.'
                raise AssertionError(message)
            return

        if len(target) == 0:
            raise AssertionError(f'Value is empty.\n{target}.')

    def assertContains(self, token, source):
        """
        Raise AssertionError if source does not contain `token`.
        """
        if token not in source:
            message = f'{source!r} does not contains {token!r}.'
            raise AssertionError(message)

    def assertNotContains(self, token, source):
        """
        Raise AssertionError if source does contain `token`.
        """
        if token in source:
            message = f'{source!r} contains {token!r}.'
            raise AssertionError(message)

    def assertTextContains(self, pattern, source):
        """
        Raise AssertionError if pattern is not found in source.
        """
        if pattern not in pattern:
            message = f'{pattern!r} not contained in\n{source!r}.'
            raise AssertionError(message)

    def assertStartsWith(self, start, source):
        """
        Raise AssertionError if `source` does not starts with `start`.
        """
        if not source.startswith(start):
            message = f'{source!r} does not starts with {start!r}'
            raise AssertionError(message)

    def assertEndsWith(self, end, source):
        """
        Raise AssertionError if `source` does not ends with `end`.
        """
        if not source.endswith(end):
            message = f'{source!r} does not end with {end!r}'
            raise AssertionError(message)

    def assertProvides(self, interface, obj):
        self.assertTrue(
            interface.providedBy(obj),
            f'Object {obj} does not provided interface {interface}.',
        )
        verifyObject(interface, obj)

    def assertNotProvides(self, interface, obj):
        self.assertFalse(
            interface.providedBy(obj),
            f'Object {obj} does not provided interface {interface}.',
        )

    def assertImplements(self, interface, klass):
        self.assertTrue(
            interface.implementedBy(klass),
            f'Class {klass} does not implements interface {interface}.',
        )

    @contextmanager
    def assertExecutionTime(self, seconds):
        """
        Check that code executes in less than `seconds` as a context manager.
        """
        start = time.time()
        yield
        duration = time.time() - start
        self.assertLess(
            duration,
            seconds,
            f'Took {duration}. Expecting less than {seconds}',
        )
