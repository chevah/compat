# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
TestCase used for Chevah project.
"""

from __future__ import absolute_import, division, print_function

import contextlib
import inspect
import os
import platform
import socket
import sys
import threading
import time
from unittest.mock import Mock, patch

import six
from bunch import Bunch
from nose import SkipTest

try:
    from twisted.internet._signals import (
        _SIGCHLDWaker,
        _SocketWaker,
        _UnixWaker,
    )
    from twisted.internet.defer import Deferred
    from twisted.python.failure import Failure
except ImportError:
    # Twisted support is optional.
    _SocketWaker = None
    _UnixWaker = None
    _SIGCHLDWaker = None

from chevah_compat import (
    DefaultAvatar,
    LocalFilesystem,
    SuperAvatar,
    process_capabilities,
    system_users,
)
from chevah_compat.administration import os_administration
from chevah_compat.testing.assertion import AssertionMixin
from chevah_compat.testing.constant import TEST_NAME_MARKER
from chevah_compat.testing.filesystem import LocalTestFilesystem
from chevah_compat.testing.mockup import mk

# For Python below 2.7 we use the separate unittest2 module.
# It comes by default in Python 2.7.
if sys.version_info[0:2] < (2, 7):
    from unittest2 import TestCase

    # Shut up you linter.
    TestCase
else:
    from unittest import TestCase

try:
    # Import reactor last in case some other modules are changing the reactor.
    from twisted.internet import reactor
except ImportError:
    reactor = None


def _get_hostname():
    """
    Return hostname as resolved by default DNS resolver.
    """
    return socket.gethostname()


class TwistedTestCase(TestCase):
    """
    Test case for Twisted specific code.

    Provides support for running deferred and start/stop the reactor during
    tests.
    """

    # Number of second to wait for a deferred to have a result.
    DEFERRED_TIMEOUT = 1

    # List of names for delayed calls which should not be considered as
    # required to wait for them when running the reactor.
    EXCEPTED_DELAYED_CALLS = []

    EXCEPTED_READERS = [_UnixWaker, _SocketWaker, _SIGCHLDWaker]

    # Scheduled event to stop waiting for a deferred.
    _reactor_timeout_call = None

    def setUp(self):
        super(TwistedTestCase, self).setUp()
        self._timeout_reached = False
        self._reactor_timeout_failure = None

    @property
    def _caller_success_member(self):
        """
        Return true if last test run was successful.
        """
        if self._outcome.result.errors:
            return False
        return True

    def tearDown(self):
        try:
            if self._caller_success_member:
                # Check for a clean reactor at shutdown, only if test
                # passed.
                self.assertIsNone(self._reactor_timeout_failure)
                self._assertReactorIsClean()
        finally:
            self._cleanReactor()
        super(TwistedTestCase, self).tearDown()

    def _reactorQueueToString(self):
        """
        Return a string representation of all delayed calls from reactor
        queue.
        """
        result = []
        for delayed in reactor.getDelayedCalls():  # noqa:cover
            result.append(six.text_type(delayed.func))
        return '\n'.join(result)

    def _threadPoolQueue(self):
        """
        Return current tasks of thread Pool, or [] when threadpool does not
        exists.

        This should only be called at cleanup as it removes elements from
        the Twisted thread queue, which will never be called.
        """
        if not reactor.threadpool:
            return []

        result = []
        while len(reactor.threadpool._team._pending):
            result.append(reactor.threadpool._team._pending.pop())
        return result

    def _threadPoolThreads(self):
        """
        Return current threads from pool, or empty list when threadpool does
        not exists.
        """
        if not reactor.threadpool:
            return []
        else:
            return reactor.threadpool.threads

    def _threadPoolWorking(self):
        """
        Return working thread from pool, or empty when threadpool does not
        exists or has no job.
        """
        if not reactor.threadpool:
            return []
        else:
            return reactor.threadpool.working

    @classmethod
    def _cleanReactor(cls):
        """
        Remove all delayed calls, readers and writers from the reactor.

        This is only for cleanup purpose and should not be used by normal
        tests.
        """
        if not reactor:
            return
        try:
            reactor.removeAll()
        except (RuntimeError, KeyError):
            # FIXME:863:
            # When running threads tests the reactor touched from the test
            # case itself which run in one tread and from the fixtures/cleanup
            # code which is executed from another thread.
            # removeAll might fail since it detects that internal state
            # is changed from other source.
            pass

        reactor.threadCallQueue = []
        for delayed_call in reactor.getDelayedCalls():
            try:
                delayed_call.cancel()
            except (ValueError, AttributeError):
                # AlreadyCancelled and AlreadyCalled are ValueError.
                # Might be canceled from the separate thread.
                # AttributeError can occur when we do multi-threading.
                pass

    def _raiseReactorTimeoutError(self, timeout):
        """
        Signal an timeout error while executing the reactor.
        """
        self._timeout_reached = True
        failure = AssertionError(
            'Reactor took more than %.2f seconds to execute.' % timeout
        )
        self._reactor_timeout_failure = failure

    def _initiateTestReactor(self, timeout):
        """
        Do the steps required to initiate a reactor for testing.
        """
        self._timeout_reached = False

        # Set up timeout.
        self._reactor_timeout_call = reactor.callLater(
            timeout, self._raiseReactorTimeoutError, timeout
        )

        # Don't start the reactor if it is already started.
        # This can happen if we prevent stop in a previous run.
        if reactor._started:
            return

        reactor._startedBefore = False
        reactor._started = False
        reactor._justStopped = False
        reactor.startRunning()

    def _iterateTestReactor(self, debug=False):
        """
        Iterate the reactor.
        """
        reactor.runUntilCurrent()
        if debug:  # noqa:cover
            # When debug is enabled with iterate using a small delay in steps,
            # to have a much better debug output.
            # Otherwise the debug messages will flood the output.
            print(
                'delayed: %s\n'
                'threads: %s\n'
                'writers: %s\n'
                'readers: %s\n'
                'threadpool size: %s\n'
                'threadpool threads: %s\n'
                'threadpool working: %s\n'
                '\n'
                % (
                    self._reactorQueueToString(),
                    reactor.threadCallQueue,
                    reactor.getWriters(),
                    reactor.getReaders(),
                    reactor.getThreadPool().q.qsize(),
                    self._threadPoolThreads(),
                    self._threadPoolWorking(),
                )
            )
            t2 = reactor.timeout()
            # For testing we want to force to reactor to wake at an
            # interval of at most 1 second.
            if t2 is None or t2 > 1:
                t2 = 0.1
            t = reactor.running and t2
            reactor.doIteration(t)
        else:
            # FIXME:4428:
            # When not executed in debug mode, some test will fail as they
            # will not spin the reactor.
            # To not slow down all the tests, we run with a very small value.
            reactor.doIteration(0.000001)

    def _shutdownTestReactor(self, prevent_stop=False):
        """
        Called at the end of a test reactor run.

        When prevent_stop=True, the reactor will not be stopped.
        """
        if not self._timeout_reached:
            # Everything fine, disable timeout.
            if (
                self._reactor_timeout_call
                and not self._reactor_timeout_call.cancelled
            ):
                self._reactor_timeout_call.cancel()

        if prevent_stop:
            # Don't continue with stop procedure.
            return

        # Let the reactor know that we want to stop reactor.
        reactor.stop()
        # Let the reactor run one more time to execute the stop code.
        reactor.iterate()

        # Set flag to fake a clean reactor.
        reactor._startedBefore = False
        reactor._started = False
        reactor._justStopped = False
        reactor.running = False
        # Start running has consumed the startup events, so we need
        # to restore them.
        reactor.addSystemEventTrigger(
            'during', 'startup', reactor._reallyStartRunning
        )

    def _assertReactorIsClean(self):
        """
        Check that the reactor has no delayed calls, readers or writers.

        This should only be called at teardown.
        """
        if reactor is None:
            return

        def raise_failure(location, reason):
            raise AssertionError(
                'Reactor is not clean. %s: %s' % (location, reason)
            )

        if reactor._started:  # noqa:cover
            # Reactor was not stopped, so stop it before raising the error.
            self._shutdownTestReactor()
            raise AssertionError('Reactor was not stopped.')

        # Look at threads queue.
        if len(reactor.threadCallQueue) > 0:
            raise_failure('queued threads', reactor.threadCallQueue)

        if reactor.threadpool and len(reactor.threadpool.working) > 0:
            raise_failure('active threads', reactor.threadCallQueue)

        pool_queue = self._threadPoolQueue()
        if pool_queue:
            raise_failure('threadpoool queue', pool_queue)

        if self._threadPoolWorking():
            raise_failure('threadpoool working', self._threadPoolWorking())

        if self._threadPoolThreads():
            raise_failure('threadpoool threads', self._threadPoolThreads())

        if len(reactor.getWriters()) > 0:  # noqa:cover
            raise_failure('writers', six.text_type(reactor.getWriters()))

        for reader in reactor.getReaders():
            excepted = False
            for reader_type in self.EXCEPTED_READERS:
                if isinstance(reader, reader_type):
                    excepted = True
                    break
            if not excepted:  # noqa:cover
                raise_failure('readers', six.text_type(reactor.getReaders()))

        for delayed_call in reactor.getDelayedCalls():
            if delayed_call.active():
                delayed_str = self._getDelayedCallName(delayed_call)
                if delayed_str in self.EXCEPTED_DELAYED_CALLS:
                    continue
                raise_failure('delayed calls', delayed_str)

    def _runDeferred(
        self, deferred, timeout=None, debug=False, prevent_stop=False
    ):
        """
        This is low level method. In most tests you would like to use
        `getDeferredFailure` or `getDeferredResult`.

        Run the deferred in the reactor loop.

        Starts the reactor, waits for deferred execution,
        raises error in timeout, stops the reactor.

        This will do recursive calls, in case the original deferred returns
        another deferred.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            self._runDeferred(deferred)

            self.assertIsNotFailure(deferred)
            self.assertEqual('something', deferred.result)
        """
        if not isinstance(deferred, Deferred):
            raise AssertionError('This is not a deferred.')

        if timeout is None:
            timeout = self.DEFERRED_TIMEOUT

        try:
            self._initiateTestReactor(timeout=timeout)
            self._executeDeferred(deferred, timeout, debug=debug)
        finally:
            self._shutdownTestReactor(prevent_stop=prevent_stop)

    def _executeDeferred(self, deferred, timeout, debug):
        """
        Does the actual deferred execution.
        """
        if not deferred.called:
            deferred_done = False
            while not deferred_done:
                self._iterateTestReactor(debug=debug)
                deferred_done = deferred.called

                if self._timeout_reached:
                    raise AssertionError(
                        'Deferred took more than %d to execute.' % timeout
                    )

        # Check executing all deferred from chained callbacks.
        result = deferred.result
        while isinstance(result, Deferred):
            self._executeDeferred(result, timeout=timeout, debug=debug)
            result = deferred.result

    def executeReactor(self, timeout=None, debug=False, run_once=False):
        """
        Run reactor until no more delayed calls, readers or
        writers or threads are in the queues.

        Set run_once=True to only run the reactor once. This is useful if
        you have persistent deferred which will be removed only at the end
        of test.

        Only use this for very high level integration code, where you don't
        have the change to get a "root" deferred.
        In most tests you would like to use one of the
        `getDeferredFailure` or `getDeferredResult`.

        Usage::

            protocol = mk.makeFTPProtocol()
            transport = mk.makeStringTransportProtocol()
            protocol.makeConnection(transport)
            transport.protocol = protocol

            protocol.lineReceived('FEAT')
            self.executeReactor()
            result = transport.value()

            self.assertStartsWith('211-Features:\n', result)
        """
        if timeout is None:
            timeout = self.DEFERRED_TIMEOUT

        self._initiateTestReactor(timeout=timeout)

        # Set it to True to enter the first loop.
        have_callbacks = True
        while have_callbacks and not self._timeout_reached:
            self._iterateTestReactor(debug=debug)

            have_callbacks = False

            # Check for active jobs in thread pool.
            if reactor.threadpool:
                if reactor.threadpool.working or (
                    reactor.threadpool.q.qsize() > 0
                ):
                    time.sleep(0.01)
                    have_callbacks = True
                    continue

            # Look at delayed calls.
            for delayed in reactor.getDelayedCalls():
                # We skip our own timeout call.
                if delayed is self._reactor_timeout_call:
                    continue
                if not delayed.func:
                    # Was already called.
                    continue
                delayed_str = self._getDelayedCallName(delayed)
                is_exception = False
                for excepted_callback in self.EXCEPTED_DELAYED_CALLS:
                    if excepted_callback in delayed_str:
                        is_exception = True
                if not is_exception:
                    # No need to look for other delayed calls.
                    have_callbacks = True
                    break

            # No need to look for other things as we already know that we need
            # to wait at least for delayed calls.
            if have_callbacks:
                continue

            if run_once:
                if have_callbacks:
                    raise AssertionError(
                        'Reactor queue still contains delayed deferred.\n'
                        '%s' % (self._reactorQueueToString())
                    )
                break

            # Look at writers buffers:
            if len(reactor.getWriters()) > 0:
                have_callbacks = True
                continue

            for reader in reactor.getReaders():
                have_callbacks = True
                for excepted_reader in self.EXCEPTED_READERS:
                    if isinstance(reader, excepted_reader):
                        have_callbacks = False
                        break
                if have_callbacks:
                    break

            if have_callbacks:
                continue

            # Look at threads queue and active thread.
            if len(reactor.threadCallQueue) > 0:
                have_callbacks = True
                continue
            if reactor.threadpool and len(reactor.threadpool.working) > 0:
                have_callbacks = True
                continue

        self._shutdownTestReactor()

    def executeDelayedCalls(self, timeout=None, debug=False):
        """
        Run the reactor until no more delayed calls are scheduled.

        This will wait for delayed calls to be executed and will not stop
        the reactor.
        """
        if timeout is None:
            timeout = self.DEFERRED_TIMEOUT

        self._initiateTestReactor(timeout=timeout)
        while not self._timeout_reached:
            self._iterateTestReactor(debug=debug)
            delayed_calls = reactor.getDelayedCalls()
            try:
                delayed_calls.remove(self._reactor_timeout_call)
            except ValueError:  # noqa:cover
                # Timeout might be no longer be there.
                pass
            if not delayed_calls:
                break
        self._shutdownTestReactor(prevent_stop=True)
        if self._reactor_timeout_failure is not None:
            self._reactor_timeout_failure = None
            # We stop the reactor on failures.
            self._shutdownTestReactor()
            raise AssertionError(
                'executeDelayedCalls took more than %s' % (timeout,)
            )

    def executeReactorUntil(
        self, callable, timeout=None, debug=False, prevent_stop=True
    ):
        """
        Run the reactor until callable returns `True`.
        """
        if timeout is None:
            timeout = self.DEFERRED_TIMEOUT

        self._initiateTestReactor(timeout=timeout)

        while not self._timeout_reached:
            self._iterateTestReactor(debug=debug)
            if callable(reactor):
                break

        self._shutdownTestReactor(prevent_stop=prevent_stop)

    def iterateReactor(self, count=1, timeout=None, debug=False):
        """
        Iterate the reactor without stopping it.
        """
        iterations = [False] * (count - 1)
        iterations.append(True)
        self.executeReactorUntil(
            lambda _: iterations.pop(0), timeout=timeout, debug=debug
        )

    def iterateReactorWithStop(self, count=1, timeout=None, debug=False):
        """
        Iterate the reactor and stop it at the end.
        """
        iterations = [False] * (count - 1)
        iterations.append(True)
        self.executeReactorUntil(
            lambda _: iterations.pop(0),
            timeout=timeout,
            debug=debug,
            prevent_stop=False,
        )

    def iterateReactorForSeconds(self, duration=1, debug=False):
        """
        Iterate the reactor for `duration` seconds..
        """
        start = time.time()

        self.executeReactorUntil(
            lambda _: time.time() - start > duration,
            timeout=duration + 0.1,
            debug=debug,
            prevent_stop=False,
        )

    def _getDelayedCallName(self, delayed_call):
        """
        Return a string representation of the delayed call.
        """
        raw_name = six.text_type(delayed_call.func)
        raw_name = raw_name.replace('<function ', '')
        raw_name = raw_name.replace('<bound method ', '')
        return raw_name.split(' ', 1)[0].split('.')[-1]

    def getDeferredFailure(
        self, deferred, timeout=None, debug=False, prevent_stop=False
    ):
        """
        Run the deferred and return the failure.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            failure = self.getDeferredFailure(deferred)

            self.assertFailureType(AuthenticationError, failure)
        """
        self._runDeferred(
            deferred, timeout=timeout, debug=debug, prevent_stop=prevent_stop
        )
        self.assertIsFailure(deferred)
        failure = deferred.result
        self.ignoreFailure(deferred)
        return failure

    def successResultOf(self, deferred):
        """
        Return the current success result of C{deferred} or raise
        C{self.failException}.

        @param deferred: A L{Deferred<twisted.internet.defer.Deferred>} which
            has a success result.  This means
            L{Deferred.callback<twisted.internet.defer.Deferred.callback>} or
            L{Deferred.errback<twisted.internet.defer.Deferred.errback>} has
            been called on it and it has reached the end of its callback chain
            and the last callback or errback returned a
            non-L{failure.Failure}.
        @type deferred: L{Deferred<twisted.internet.defer.Deferred>}

        @raise SynchronousTestCase.failureException: If the
            L{Deferred<twisted.internet.defer.Deferred>} has no result or has
            a failure result.

        @return: The result of C{deferred}.
        """
        # FIXME:1370:
        # Remove / re-route this code after upgrading to Twisted 13.0.
        result = []
        deferred.addBoth(result.append)
        if not result:
            self.fail(
                'Success result expected on %r, found no result instead'
                % (deferred,)
            )
        elif isinstance(result[0], Failure):
            self.fail(
                'Success result expected on %r, '
                'found failure result instead:\n%s'
                % (deferred, result[0].getBriefTraceback())
            )
        else:
            return result[0]

    def failureResultOf(self, deferred, *expectedExceptionTypes):
        """
        Return the current failure result of C{deferred} or raise
        C{self.failException}.

        @param deferred: A L{Deferred<twisted.internet.defer.Deferred>} which
            has a failure result.  This means
            L{Deferred.callback<twisted.internet.defer.Deferred.callback>} or
            L{Deferred.errback<twisted.internet.defer.Deferred.errback>} has
            been called on it and it has reached the end of its callback chain
            and the last callback or errback raised an exception or returned a
            L{failure.Failure}.
        @type deferred: L{Deferred<twisted.internet.defer.Deferred>}

        @param expectedExceptionTypes: Exception types to expect - if
            provided, and the the exception wrapped by the failure result is
            not one of the types provided, then this test will fail.

        @raise SynchronousTestCase.failureException: If the
            L{Deferred<twisted.internet.defer.Deferred>} has no result, has a
            success result, or has an unexpected failure result.

        @return: The failure result of C{deferred}.
        @rtype: L{failure.Failure}
        """
        # FIXME:1370:
        # Remove / re-route this code after upgrading to Twisted 13
        result = []
        deferred.addBoth(result.append)
        if not result:
            self.fail(
                'Failure result expected on %r, found no result instead'
                % (deferred,)
            )
        elif not isinstance(result[0], Failure):
            self.fail(
                'Failure result expected on %r, '
                'found success result (%r) instead' % (deferred, result[0])
            )
        elif expectedExceptionTypes and not result[0].check(
            *expectedExceptionTypes
        ):
            expectedString = ' or '.join(
                [f'{t.__module__}.{t.__name__}' for t in expectedExceptionTypes]
            )

            self.fail(
                'Failure of type (%s) expected on %r, '
                'found type %r instead: %s'
                % (
                    expectedString,
                    deferred,
                    result[0].type,
                    result[0].getBriefTraceback(),
                )
            )
        else:
            return result[0]

    def assertNoResult(self, deferred):
        """
        Assert that C{deferred} does not have a result at this point.

        If the assertion succeeds, then the result of C{deferred} is left
        unchanged. Otherwise, any L{failure.Failure} result is swallowed.

        @param deferred: A L{Deferred<twisted.internet.defer.Deferred>}
            without a result.  This means that neither
            L{Deferred.callback<twisted.internet.defer.Deferred.callback>} nor
            L{Deferred.errback<twisted.internet.defer.Deferred.errback>} has
            been called, or that the
            L{Deferred<twisted.internet.defer.Deferred>} is waiting on another
            L{Deferred<twisted.internet.defer.Deferred>} for a result.
        @type deferred: L{Deferred<twisted.internet.defer.Deferred>}

        @raise SynchronousTestCase.failureException: If the
            L{Deferred<twisted.internet.defer.Deferred>} has a result.
        """
        # FIXME:1370:
        # Remove / re-route this code after upgrading to Twisted 13
        result = []

        def cb(res):
            result.append(res)
            return res

        deferred.addBoth(cb)
        if result:
            # If there is already a failure, the self.fail below will
            # report it, so swallow it in the deferred
            deferred.addErrback(lambda _: None)
            self.fail(
                'No result expected on %r, found %r instead'
                % (deferred, result[0])
            )

    def getDeferredResult(
        self, deferred, timeout=None, debug=False, prevent_stop=False
    ):
        """
        Run the deferred and return the result.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            result = self.getDeferredResult(deferred)

            self.assertEqual('something', result)
        """
        self._runDeferred(
            deferred, timeout=timeout, debug=debug, prevent_stop=prevent_stop
        )
        self.assertIsNotFailure(deferred)
        return deferred.result

    def assertWasCalled(self, deferred):
        """
        Check that deferred was called.
        """
        if not deferred.called:
            raise AssertionError('This deferred was not called yet.')

    def ignoreFailure(self, deferred):
        """
        Ignore the current failure on the deferred.

        It transforms an failure into result `None` so that the failure
        will not be raised at reactor shutdown for not being handled.
        """
        deferred.addErrback(lambda failure: None)

    def assertIsFailure(self, deferred):
        """
        Check that deferred is a failure.
        """
        if not isinstance(deferred.result, Failure):
            raise AssertionError('Deferred is not a failure.')

    def assertIsNotFailure(self, deferred):
        """
        Raise assertion error if deferred is a Failure.

        The failed deferred is handled by this method, to avoid propagating
        the error into the reactor.
        """
        self.assertWasCalled(deferred)

        if isinstance(deferred.result, Failure):
            error = deferred.result
            self.ignoreFailure(deferred)
            raise AssertionError('Deferred contains a failure: %s' % (error))


def _get_os_version():
    """
    On non-Linux this is just the os_name.

    On Linux is the distribution name and the version.

    On Windows it is the `nt` followed by the major and minor NT version.
    It is not the marketing name.
    We only support the Windows NT family.
    See: https://en.wikipedia.org/wiki/Windows_NT#Releases

    On OSX it returns `osx` followed by the version.
    It is not the version of the underlying Darwin OS.
    See: https://en.wikipedia.org/wiki/MacOS#Release_history
    """
    if os.name == 'nt':
        parts = platform.version().split('.')
        return 'nt-%s.%s' % (parts[0], parts[1])

    # We are now in Unix zone.
    os_name = os.uname()[0].lower()

    if os_name == 'darwin':
        parts = platform.mac_ver()[0].split('.')
        return 'osx-%s.%s' % (parts[0], parts[1])

    if os_name == 'sunos':
        parts = platform.release().split('.')
        return 'solaris-%s' % (parts[1],)

    if os_name == 'aix':  # noqa:cover
        return 'aix-%s.%s' % (platform.version(), platform.release())

    if os_name != 'linux':
        return process_capabilities.os_name

    # We delay the import as it will call lsb_release.
    import distro

    distro_name = distro.id()
    if distro_name == 'arch':
        # Arch has no version.
        return 'arch'

    if distro_name in ['centos', 'ol']:
        # Normalize all RHEL variants.
        distro_name = 'rhel'

    distro_version = distro.version().split('.', 1)[0]

    return '%s-%s' % (distro_name, distro_version)


def _get_cpu_type():
    """
    Return the CPU type as used in the brink.sh script.
    """
    base = platform.processor()
    if base == 'aarch64':
        return 'arm64'

    if base == 'x86_64':
        return 'x64'

    return base


_CI_NAMES = Bunch(
    LOCAL='local',
    GITHUB='github-actions',
    TRAVIS='travis',
    BUILDBOT='buildbot',
    UNKNOWN='unknown-ci',
    AZURE='azure-pipelines',
)


def _get_ci_name():
    """
    Return the name of the CI on which the tests are currently executed.
    """
    if os.environ.get('BUILDBOT', '').lower() == 'true':
        return _CI_NAMES.BUILDBOT

    if os.environ.get('GITHUB_ACTIONS', '').lower() == 'true':
        return _CI_NAMES.GITHUB

    if os.environ.get('TRAVIS', '').lower() == 'true':
        return _CI_NAMES.TRAVIS

    if os.environ.get('INFRASTRUCTURE', '') == 'AZUREPIPELINES':
        return _CI_NAMES.AZURE

    if os.environ.get('CI', '').lower() == 'true':
        return _CI_NAMES.UNKNOWN

    return _CI_NAMES.LOCAL


class ChevahTestCase(TwistedTestCase, AssertionMixin):
    """
    Test case for Chevah tests.

    Checks that temporary folder is clean at exit.
    """

    os_name = process_capabilities.os_name
    os_family = process_capabilities.os_family
    os_version = _get_os_version()
    cpu_type = process_capabilities.cpu_type
    ci_name = _get_ci_name()
    CI = _CI_NAMES
    TEST_LANGUAGE = os.getenv('TEST_LANG', 'EN')

    # List of partial thread names to ignore during the tearDown.
    # No need for the full thread name
    excepted_threads = [
        'MainThread',
        'threaded_reactor',
        'GlobalPool-WorkerHandler',
        'GlobalPool-TaskHandler',
        'GlobalPool-ResultHandler',
        'PoolThread-twisted.internet.reactor',
    ]

    # We assume that hostname does not change during test and this
    # should save a few DNS queries.
    hostname = _get_hostname()

    Bunch = Bunch
    Mock = Mock
    #: Obsolete. Please use self.patch and self.patchObject.
    Patch = patch

    _environ_user = None
    _drop_user = '-'

    def setUp(self):
        super(ChevahTestCase, self).setUp()
        self.__cleanup__ = []
        self._cleanup_stack = []
        self._teardown_errors = []
        self.test_segments = None

    def tearDown(self):
        self.callCleanup()
        self._checkTemporaryFiles()
        threads = threading.enumerate()
        if len(threads) > 1:
            for thread in threads:
                thread_name = thread.getName()
                if self._isExceptedThread(thread_name):
                    continue
                self._teardown_errors.append(
                    AssertionError(
                        'There are still active threads, '
                        'beside the main thread: %s - %s'
                        % (thread_name, threads)
                    )
                )

        super(ChevahTestCase, self).tearDown()

        errors, self._teardown_errors = self._teardown_errors, None
        if errors:
            raise AssertionError('Cleanup errors: %r' % (errors,))

    def _isExceptedThread(self, name):
        """
        Return `True` if is OK for thread to exist after test is done.
        """
        for exception in self.excepted_threads:
            if name in exception:
                return True

            if exception in name:
                return True

        return False

    def addCleanup(self, function, *args, **kwargs):
        """
        Overwrite unit-test behaviour to run cleanup method before tearDown.
        """
        self.__cleanup__.append((function, args, kwargs))

    def callCleanup(self):
        """
        Call all cleanup methods.

        If a cleanup fails, the next cleanups will continue to be called and
        the first failure is raised.
        """
        for function, args, kwargs in reversed(self.__cleanup__):
            try:
                function(*args, **kwargs)
            except Exception as error:  # noqa:cover
                self._teardown_errors.append(error, function, args, kwargs)

        self.__cleanup__ = []

    def enterCleanup(self):
        """
        Called when start using stacked cleanups.
        """
        self._cleanup_stack.append(self.__cleanup__)
        self.__cleanup__ = []

    def exitCleanup(self):
        """
        To be called at the end of a stacked cleanup.
        """
        self.callCleanup()
        self.__cleanup__ = self._cleanup_stack.pop()

    @contextlib.contextmanager
    def stackedCleanup(self):
        """
        Context manager for stacked cleanups.
        """
        try:
            self.enterCleanup()
            yield
        finally:
            self.exitCleanup()

    def _checkTemporaryFiles(self):
        """
        Check that no temporary files or folders are present.
        """
        # FIXME:922:
        # Move all filesystem checks into a specialized class
        if self.test_segments:
            if mk.fs.isFolder(self.test_segments):
                mk.fs.deleteFolder(self.test_segments, recursive=True)
            else:
                mk.fs.deleteFile(self.test_segments)

        checks = [self.assertTempIsClean, self.assertWorkingFolderIsClean]

        errors = []
        for check in checks:
            try:
                check()
            except AssertionError as error:
                errors.append(str(error))

        if errors:  # noqa:cover
            self._teardown_errors.append(
                AssertionError(
                    'There are temporary files or folders left over.\n %s'
                    % ('\n'.join(errors))
                )
            )

    def shortDescription(self):  # noqa:cover
        """
        The short description for the test.

        bla.bla.tests. is removed.
        The format is customized for Chevah Nose runner.

        This is only called when we run with -v or we show the error.
        """
        class_name = six.text_type(self.__class__)[8:-2]
        class_name = class_name.replace('.Test', ':Test')
        tests_start = class_name.find('.tests.') + 7
        class_name = class_name[tests_start:]

        return '%s - %s.%s' % (
            self._testMethodName,
            class_name,
            self._testMethodName,
        )

    def assertRaises(self, exception_class, callback=None, *args, **kwargs):
        """
        Wrapper around the stdlib call to allow non-context usage.
        """
        super_assertRaises = super(ChevahTestCase, self).assertRaises
        if callback is None:
            return super_assertRaises(exception_class)

        with super_assertRaises(exception_class) as context:
            callback(*args, **kwargs)

        return context.exception

    def assertSequenceEqual(self, first, second, msg, seq_type):
        super(ChevahTestCase, self).assertSequenceEqual(
            first, second, msg, seq_type
        )

        for first_element, second_element in zip(first, second):
            self.assertEqual(first_element, second_element)

    def assertDictEqual(self, first, second, msg):
        super(ChevahTestCase, self).assertDictEqual(first, second, msg)

        first_keys = sorted(first.keys())
        second_keys = sorted(second.keys())
        first_values = [first[key] for key in first_keys]
        second_values = [second[key] for key in second_keys]
        self.assertSequenceEqual(first_keys, second_keys, msg, list)
        self.assertSequenceEqual(first_values, second_values, msg, list)

    def assertSetEqual(self, first, second, msg):
        super(ChevahTestCase, self).assertSetEqual(first, second, msg)

        first_elements = sorted(first)
        second_elements = sorted(second)
        self.assertSequenceEqual(first_elements, second_elements, msg, list)

    def _baseAssertEqual(self, first, second, msg=None):
        """
        Update to stdlib to make sure we don't compare str with unicode.
        """
        if isinstance(first, six.text_type) and not isinstance(
            second, six.text_type
        ):  # noqa:cover
            if not msg:
                msg = 'First is unicode while second is str for "%s".' % (
                    first,
                )
            raise AssertionError(msg.encode('utf-8'))

        if not isinstance(first, six.text_type) and isinstance(
            second, six.text_type
        ):  # noqa:cover
            if not msg:
                msg = 'First is str while second is unicode for "%s".' % (
                    first,
                )
            raise AssertionError(msg.encode('utf-8'))

        return super(ChevahTestCase, self)._baseAssertEqual(
            first, second, msg=msg
        )

    @staticmethod
    def getHostname():
        """
        Return the hostname of the current system.
        """
        return _get_hostname()

    @classmethod
    def initialize(cls, drop_user):
        """
        Initialize the testing environment.
        """
        cls._drop_user = drop_user
        os.environ['DROP_USER'] = drop_user

        if 'LOGNAME' in os.environ and 'USER' not in os.environ:
            os.environ['USER'] = os.environ['LOGNAME']

        if 'USER' in os.environ and 'USERNAME' not in os.environ:
            os.environ['USERNAME'] = os.environ['USER']

        if 'USERNAME' in os.environ and 'USER' not in os.environ:
            os.environ['USER'] = os.environ['USERNAME']

        cls._environ_user = os.environ['USER']

        cls.cleanTemporaryFolder()

    @classmethod
    def dropPrivileges(cls):
        """Drop privileges to normal users."""
        if cls._drop_user == '-':
            return

        os.environ['USERNAME'] = cls._drop_user
        os.environ['USER'] = cls._drop_user
        # Test suite should be started as root and we drop effective user
        # privileges.
        system_users.dropPrivileges(username=cls._drop_user)

    @staticmethod
    def skipTest(message=''):
        """Return a SkipTest exception."""
        return SkipTest(message)

    @staticmethod
    def patch(*args, **kwargs):
        """
        Helper for generic patching.
        """
        return patch(*args, **kwargs)

    @staticmethod
    def patchObject(*args, **kwargs):
        """
        Helper for patching objects.
        """
        return patch.object(*args, **kwargs)

    def now(self):
        """
        Return current Unix timestamp.
        """
        return time.time()

    @classmethod
    def cleanTemporaryFolder(cls):
        """
        Clean all test files from temporary folder.

        Return a list of members which were removed.
        """
        return cls._cleanFolder(mk.fs.temp_segments)

    @classmethod
    def cleanWorkingFolder(cls):
        path = mk.fs.getAbsoluteRealPath('.')
        segments = mk.fs.getSegmentsFromRealPath(path)
        return cls._cleanFolder(segments, only_marked=True)

    @classmethod
    def _cleanFolder(cls, folder_segments, only_marked=False):
        """
        Clean all test files from folder_segments.

        Return a list of members which were removed.
        """
        if not mk.fs.exists(folder_segments):
            return []

        # In case we are running the test suite as super user,
        # we use super filesystem for cleaning.
        if cls._environ_user == cls._drop_user:
            temp_avatar = SuperAvatar()
        else:
            temp_avatar = DefaultAvatar()

        temp_filesystem = LocalFilesystem(avatar=temp_avatar)
        temp_members = []
        for member in temp_filesystem.getFolderContent(folder_segments):
            if only_marked and member.find(TEST_NAME_MARKER) == -1:
                continue
            temp_members.append(member)
            segments = folder_segments[:] + [member]
            if temp_filesystem.isFolder(segments):
                temp_filesystem.deleteFolder(segments, recursive=True)
                continue

            try:
                temp_filesystem.deleteFile(segments)
            except Exception:
                # FIXME:688:
                # If this is a link to a broken folder,
                # it is detected as a file,
                # but on Windows it is a folder.
                temp_filesystem.deleteFolder(segments, recursive=True)

        return temp_members

    @classmethod
    def getPeakMemoryUsage(cls):
        """
        Return maximum memory usage in kilo bytes.
        """
        if cls.os_family == 'posix':
            import resource

            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        elif cls.os_family == 'nt':
            from wmi import WMI

            local_wmi = WMI('.')

            query = (
                'SELECT PeakWorkingSetSize '
                'FROM Win32_Process '
                'WHERE Handle=%d' % os.getpid()
            )
            result = local_wmi.query(query.encode('utf-8'))
            peak_working_set_size = int(result[0].PeakWorkingSetSize)
            # FIXME:2099:
            # Windows XP reports value in bytes, instead of Kilobytes.
            return int(peak_working_set_size)
        else:
            raise AssertionError('OS not supported.')

    def folderInTemp(self, *args, **kwargs):
        """
        Create a folder in the default temp folder and mark it for cleanup.
        """
        kwargs['cleanup'] = self.addCleanup
        return mk.fs.folderInTemp(*args, **kwargs)

    def fileInTemp(self, *args, **kwargs):
        """
        Create a file in the default temp folder and mark it for cleanup.
        """
        kwargs['cleanup'] = self.addCleanup
        return mk.fs.fileInTemp(*args, **kwargs)

    def assertIn(self, target, source):
        """
        Overwrite stdlib to swap the arguments.
        """
        if source not in target:
            message = '%s not in %s.' % (repr(source), repr(target))
            raise AssertionError(message.encode('utf-8'))

    def assertIsInstance(self, expected_type, value, msg=None):
        """
        Raise an exception if `value` is not an instance of `expected_type`
        """
        # In Python 2.7 isInstance is already defined, but with swapped
        # arguments.
        if not inspect.isclass(expected_type):
            expected_type, value = value, expected_type

        if not isinstance(value, expected_type):
            raise AssertionError(
                'Expecting type %s, but got %s. %s'
                % (expected_type, type(value), msg)
            )

    def tempPath(self, prefix='', suffix='', win_encoded=False):
        """
        Return (path, segments) for a path which is not created yet.
        """
        path, segments = mk.fs.makePathInTemp(prefix=prefix, suffix=suffix)

        if self.os_family == 'nt' and win_encoded:
            path = mk.fs.getEncodedPath(path)

        return path, segments

    def tempPathCleanup(self, prefix='', suffix='', win_encoded=False):
        """
        Return (path, segments) for a path which is not created yet but which
        will be automatically removed.
        """
        path, segments = mk.fs.pathInTemp(
            cleanup=self.addCleanup, prefix=prefix, suffix=suffix
        )

        if self.os_family == 'nt' and win_encoded:
            path = mk.fs.getEncodedPath(path)

        return path, segments

    def tempFile(
        self, content='', prefix='', suffix='', cleanup=True, win_encoded=False
    ):
        """
        Return (path, segments) for a new file created in temp which is
        auto cleaned.

        When `win_encoded` is True, it will return the low-level Windows path.
        """
        segments = mk.fs.createFileInTemp(prefix=prefix, suffix=suffix)
        path = mk.fs.getRealPathFromSegments(segments)

        if isinstance(content, six.text_type):
            content = content.encode('utf-8')

        if cleanup:
            self.addCleanup(mk.fs.deleteFile, segments)

        try:
            opened_file = mk.fs.openFileForWriting(segments)
            opened_file.write(content)
        finally:
            opened_file.close()

        if self.os_family == 'nt' and win_encoded:
            path = mk.fs.getEncodedPath(path)

        return (path, segments)

    def tempFolder(self, name=None, prefix='', suffix=''):
        """
        Create a new temp folder and return its path and segments, which is
        auto cleaned.
        """
        segments = mk.fs.createFolderInTemp(
            foldername=name, prefix=prefix, suffix=suffix
        )
        path = mk.fs.getRealPathFromSegments(segments)
        self.addCleanup(mk.fs.deleteFolder, segments, recursive=True)
        return (path, segments)


class FileSystemTestCase(ChevahTestCase):
    """
    Common test case for all file-system tests using a real OS account.
    """

    @classmethod
    def setUpClass(cls):
        # FIXME:924:
        # Disabled when we can not find the home folder path.
        if not process_capabilities.get_home_folder:
            raise cls.skipTest()

        super(FileSystemTestCase, cls).setUpClass()

        cls.os_user = cls.setUpTestUser()

        home_folder_path = system_users.getHomeFolder(
            username=cls.os_user.name, token=cls.os_user.token
        )

        cls.avatar = mk.makeFilesystemOSAvatar(
            name=cls.os_user.name,
            home_folder_path=home_folder_path,
            token=cls.os_user.token,
        )
        cls.filesystem = LocalFilesystem(avatar=cls.avatar)

    @classmethod
    def tearDownClass(cls):
        if not cls.os_user.windows_create_local_profile:
            os_administration.deleteHomeFolder(cls.os_user)
        os_administration.deleteUser(cls.os_user)

        super(FileSystemTestCase, cls).tearDownClass()

    @classmethod
    def setUpTestUser(cls):
        """
        Set-up OS user for file system testing.
        """
        from chevah_compat.testing import TEST_ACCOUNT_GROUP

        user = mk.makeTestUser(home_group=TEST_ACCOUNT_GROUP)
        os_administration.addUser(user)
        return user

    def setUp(self):
        super(FileSystemTestCase, self).setUp()
        # Initialized only to clean the home folder.
        test_filesystem = LocalTestFilesystem(avatar=self.avatar)
        test_filesystem.cleanHomeFolder()


class OSAccountFileSystemTestCase(FileSystemTestCase):
    """
    Test case for tests that need a dedicated local OS account present.
    """

    #: User will be created before running the test case and removed on
    #: teardown.
    CREATE_TEST_USER = None

    @classmethod
    def setUpTestUser(cls):
        """
        Add `CREATE_TEST_USER` to local OS.
        """
        os_administration.addUser(cls.CREATE_TEST_USER)
        return cls.CREATE_TEST_USER
