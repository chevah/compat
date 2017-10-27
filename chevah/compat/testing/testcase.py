# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
TestCase used for Chevah project.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from six import text_type
from six.moves import range
import inspect
import threading
import os
import platform
import socket
import sys
import time

from bunch import Bunch
from mock import patch, Mock
from nose import SkipTest
try:
    from twisted.internet.defer import Deferred
    from twisted.internet.posixbase import (
        _SocketWaker, _UnixWaker, _SIGCHLDWaker
        )
    from twisted.python.failure import Failure
except ImportError:
    # Twisted support is optional.
    _SocketWaker = None
    _UnixWaker = None
    _SIGCHLDWaker = None

from chevah.compat import (
    DefaultAvatar,
    LocalFilesystem,
    process_capabilities,
    system_users,
    SuperAvatar,
    )
from chevah.compat.administration import os_administration
from chevah.compat.testing.assertion import AssertionMixin
from chevah.compat.testing.mockup import mk
from chevah.compat.testing.constants import (
    TEST_NAME_MARKER,
    )
from chevah.compat.testing.filesystem import LocalTestFilesystem

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

    EXCEPTED_READERS = [
        _UnixWaker,
        _SocketWaker,
        _SIGCHLDWaker,
        ]

    def setUp(self):
        super(TwistedTestCase, self).setUp()
        self._timeout_reached = False
        self._reactor_timeout_failure = None

    @property
    def _caller_success_member(self):
        """
        Retrieve the 'success' member from the None test case.
        """
        success = None
        for i in range(2, 6):
            try:
                success = inspect.stack()[i][0].f_locals['success']
                break
            except KeyError:
                success = None
        if success is None:
            raise AssertionError('Failed to find "success" attribute.')
        return success

    def tearDown(self):
        try:
            if self._caller_success_member:
                # Check for a clean reactor at shutdown, only if test
                # passed.
                self.assertIsNone(self._reactor_timeout_failure)
                self.assertReactorIsClean()
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
            result.append(text_type(delayed.func))
        return '\n'.join(result)

    def _threadPoolQueueSize(self):
        """
        Return current size of thread Pool, or None when threadpool does not
        exists.
        """
        if not reactor.threadpool:
            return 0
        else:
            return reactor.threadpool.q.qsize()

    def _threadPoolThreads(self):
        """
        Return current threads from pool, or None when threadpool does not
        exists.
        """
        if not reactor.threadpool:
            return 0
        else:
            return reactor.threadpool.threads

    def _threadPoolWorking(self):
        """
        Return working thread from pool, or None when threadpool does not
        exists.
        """
        if not reactor.threadpool:
            return 0
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
            'Reactor took more than %.2f seconds to execute.' % timeout)
        self._reactor_timeout_failure = failure

    def _initiateTestReactor(self, timeout):
        """
        Do the steps required to initiate a reactor for testing.
        """
        self._timeout_reached = False

        # Set up timeout.
        self._reactor_timeout_call = reactor.callLater(
            timeout, self._raiseReactorTimeoutError, timeout)

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
        if debug:
            # When debug is enabled with iterate using a small delay in steps,
            # to have a much better debug output.
            # Otherwise the debug messages will flood the output.
            print (
                u'delayed: %s\n'
                u'threads: %s\n'
                u'writers: %s\n'
                u'readers: %s\n'
                u'threadpool size: %s\n'
                u'threadpool threads: %s\n'
                u'threadpool working: %s\n'
                u'\n' % (
                    self._reactorQueueToString(),
                    reactor.threadCallQueue,
                    reactor.getWriters(),
                    reactor.getReaders(),
                    self._threadPoolQueueSize(),
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
            reactor.doIteration(False)

    def _shutdownTestReactor(self, prevent_stop=False):
        """
        Called at the end of a test reactor run.

        When prevent_stop=True, the reactor will not be stopped.
        """
        if not self._timeout_reached:
            # Everything fine, disable timeout.
            if not self._reactor_timeout_call.cancelled:
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
            'during', 'startup', reactor._reallyStartRunning)

    def assertReactorIsClean(self):
        """
        Check that the reactor has no delayed calls, readers or writers.
        """
        if reactor is None:
            return

        def raise_failure(location, reason):
            raise AssertionError(
                'Reactor is not clean. %s: %s' % (location, reason))

        if reactor._started:
            raise AssertionError('Reactor was not stopped.')

        # Look at threads queue.
        if len(reactor.threadCallQueue) > 0:
            raise_failure('threads', reactor.threadCallQueue)

        if self._threadPoolQueueSize() > 0:
            raise_failure('threadpoool queue', self._threadPoolQueueSize())

        if self._threadPoolWorking() > 0:
            raise_failure('threadpoool working', self._threadPoolWorking())

        if self._threadPoolThreads() > 0:
            raise_failure('threadpoool threads', self._threadPoolThreads())

        if len(reactor.getWriters()) > 0:  # noqa:cover
            raise_failure('writers', text_type(reactor.getWriters()))

        for reader in reactor.getReaders():
            excepted = False
            for reader_type in self.EXCEPTED_READERS:
                if isinstance(reader, reader_type):
                    excepted = True
                    break
            if not excepted:  # noqa:cover
                raise_failure('readers', text_type(reactor.getReaders()))

        for delayed_call in reactor.getDelayedCalls():
            if delayed_call.active():
                delayed_str = self._getDelayedCallName(delayed_call)
                if delayed_str in self.EXCEPTED_DELAYED_CALLS:
                    continue
                raise_failure('delayed calls', delayed_str)

    def runDeferred(
            self, deferred, timeout=None, debug=False, prevent_stop=False):
        """
        Run the deferred in the reactor loop.

        Starts the reactor, waits for deferred execution,
        raises error in timeout, stops the reactor.

        This will do recursive calls, in case the original deferred returns
        another deferred.

        This is low level method. In most tests you would like to use
        `getDeferredFailure` or `getDeferredResult`.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            self.runDeferred(deferred)

            self.assertIsNotFailure(deferred)
            self.assertEqual('something', deferred.result)
        """
        if not isinstance(deferred, Deferred):
            raise AssertionError('This is not a deferred.')

        if timeout is None:
            timeout = self.DEFERRED_TIMEOUT

        try:
            self._initiateTestReactor(timeout=timeout)
            self._runDeferred(deferred, timeout, debug=debug)
        finally:
            self._shutdownTestReactor(
                prevent_stop=prevent_stop)

    def _runDeferred(self, deferred, timeout, debug):
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
                        'Deferred took more than %d to execute.' % timeout)

        # Check executing all deferred from chained callbacks.
        result = deferred.result
        while isinstance(result, Deferred):
            self._runDeferred(result, timeout=timeout, debug=debug)
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
                if (
                        reactor.threadpool.working or
                        (reactor.threadpool.q.qsize() > 0)
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
                        '%s' % (self._reactorQueueToString()))
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

            # Look at threads queue.
            if len(reactor.threadCallQueue) > 0:
                have_callbacks = True
                continue

        self._shutdownTestReactor()

    def _getDelayedCallName(self, delayed_call):
        """
        Return a string representation of the delayed call.
        """
        raw_name = text_type(delayed_call.func)
        raw_name = raw_name.replace('<function ', '')
        raw_name = raw_name.replace('<bound method ', '')
        return raw_name.split(' ', 1)[0]

    def getDeferredFailure(
            self, deferred, timeout=None, debug=False, prevent_stop=False):
        """
        Run the deferred and return the failure.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            failure = self.getDeferredFailure(deferred)

            self.assertFailureType(AuthenticationError, failure)
        """
        self.runDeferred(
            deferred,
            timeout=timeout,
            debug=debug,
            prevent_stop=prevent_stop,
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
                "Success result expected on %r, found no result instead" % (
                    deferred,))
        elif isinstance(result[0], Failure):
            self.fail(
                "Success result expected on %r, "
                "found failure result instead:\n%s" % (
                    deferred, result[0].getTraceback()))
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
                "Failure result expected on %r, found no result instead" % (
                    deferred,))
        elif not isinstance(result[0], Failure):
            self.fail(
                "Failure result expected on %r, "
                "found success result (%r) instead" % (deferred, result[0]))
        elif (expectedExceptionTypes and
              not result[0].check(*expectedExceptionTypes)):
            expectedString = " or ".join([
                '.'.join((t.__module__, t.__name__)) for t in
                expectedExceptionTypes])

            self.fail(
                "Failure of type (%s) expected on %r, "
                "found type %r instead: %s" % (
                    expectedString, deferred, result[0].type,
                    result[0].getTraceback()))
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
                "No result expected on %r, found %r instead" % (
                    deferred, result[0]))

    def getDeferredResult(
            self, deferred, timeout=None, debug=False, prevent_stop=False):
        """
        Run the deferred and return the result.

        Usage::

            checker = mk.credentialsChecker()
            credentials = mk.credentials()

            deferred = checker.requestAvatarId(credentials)
            result = self.getDeferredResult(deferred)

            self.assertEqual('something', result)
        """
        self.runDeferred(
            deferred,
            timeout=timeout,
            debug=debug,
            prevent_stop=prevent_stop,
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
            error = deferred.result.value
            self.ignoreFailure(deferred)
            raise AssertionError(
                'Deferred contains a failure: %s' % (error))


def _get_os_version():
    """
    On non-Linux this is just the os_name.

    On Linux is the distribution name, without the version.

    On Windows it is the `nt` followed by the major and minor NT version.
    IS not the marketing name.
    We only support Windows NT family.
    See: https://en.wikipedia.org/wiki/Windows_NT#Releases

    On OSX it returns `osx` followed by the version.
    Is not the Darwin version.
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

    if os_name == 'aix':
        return 'aix-%s.%s' % (platform.version(), platform.release())

    if os_name != 'linux':
        return process_capabilities.os_name

    # We delay the import as it will call lsb_release.
    import ld

    distro_name = ld.id()
    if distro_name == 'arch':
        # Arch has no version.
        return 'arch'

    distro_version = ld.version().split('.', 1)[0]

    return '%s-%s' % (distro_name, distro_version)


def _get_cpu_type():
    """
    Return the CPU type as used in the paver.sh script.
    """
    base = platform.processor()
    if base == 'aarch64':
        return 'arm64'

    if base == 'x86_64':
        return 'x64'

    return base


class ChevahTestCase(TwistedTestCase, AssertionMixin):
    """
    Test case for Chevah tests.

    Checks that temporary folder is clean at exit.
    """

    os_name = process_capabilities.os_name
    os_family = process_capabilities.os_family
    os_version = _get_os_version()
    cpu_type = _get_cpu_type()

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
        self.test_segments = None

    def tearDown(self):
        self.callCleanup()
        self._checkTemporaryFiles()
        threads = threading.enumerate()
        if len(threads) > 1:
            # FIXME:1077:
            # For now we don't clean the whole reactor so Twisted is
            # an exception here.
            for thread in threads:
                thread_name = thread.getName()
                if thread_name == 'MainThread':
                    continue
                if thread_name == 'threaded_reactor':
                    continue
                if thread_name.startswith(
                        'PoolThread-twisted.internet.reactor'):
                    continue

                raise AssertionError(
                    'There are still active threads, '
                    'beside the main thread: %s - %s' % (
                        thread_name, threads))

        super(ChevahTestCase, self).tearDown()

    def addCleanup(self, function, *args, **kwargs):
        """
        Overwrite unit-test behaviour to run cleanup method before tearDown.
        """
        self.__cleanup__.append((function, args, kwargs))

    def callCleanup(self):
        """
        Call all cleanup methods.
        """
        for function, args, kwargs in reversed(self.__cleanup__):
            function(*args, **kwargs)
        self.__cleanup__ = []

    def _checkTemporaryFiles(self):
        """
        Check that no temporary files or folders are present.
        """
        # FIXME:922:
        # Move all filesystem checks into a specialized class
        if self.test_segments:
            if mk.fs.isFolder(self.test_segments):
                mk.fs.deleteFolder(
                    self.test_segments, recursive=True)
            else:
                mk.fs.deleteFile(self.test_segments)

        checks = [
            self.assertTempIsClean,
            self.assertWorkingFolderIsClean,
            ]

        errors = []
        for check in checks:
            try:
                check()
            except AssertionError as error:
                errors.append(error.message)

        if errors:
            raise AssertionError(
                'There are temporary files or folders left over.\n %s' % (
                    '\n'.join(errors)))

    def shortDescription(self):  # noqa:cover
        """
        The short description for the test.

        bla.bla.tests. is removed.
        The format is customized for Chevah Nose runner.

        This is only called when we run with -v or we show the error.
        """
        class_name = text_type(self.__class__)[8:-2]
        class_name = class_name.replace('.Test', ':Test')
        tests_start = class_name.find('.tests.') + 7
        class_name = class_name[tests_start:]

        return "%s - %s.%s" % (
            self._testMethodName,
            class_name,
            self._testMethodName)

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
    def haveSuperPowers(cls):
        '''Return true if we can access privileged OS operations.'''
        if os.name == 'posix' and cls._drop_user == '-':
            return False
        if not process_capabilities.impersonate_local_account:
            return False
        return True

    @classmethod
    def dropPrivileges(cls):
        '''Drop privileges to normal users.'''
        if cls._drop_user == '-':
            return

        os.environ['USERNAME'] = cls._drop_user
        os.environ['USER'] = cls._drop_user
        # Test suite should be started as root and we drop effective user
        # privileges.
        system_users.dropPrivileges(username=cls._drop_user)

    @staticmethod
    def skipTest(message=''):
        '''Return a SkipTest exception.'''
        return SkipTest(message)

    @property
    def _caller_success_member(self):
        '''Retrieve the 'success' member from the test case.'''
        success_state = None
        # We search starting with second stack, since first stack is the
        # current stack and we don't care about it.
        for level in inspect.stack()[1:]:
            try:
                success_state = level[0].f_locals['success']
                break
            except KeyError:
                success_state = None
        if success_state is None:
            raise AssertionError('Failed to find "success" attribute.')
        return success_state

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
        return cls._cleanFolder(segments)

    @classmethod
    def _cleanFolder(cls, folder_segments):
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
        for member in (temp_filesystem.getFolderContent(folder_segments)):
            if member.find(TEST_NAME_MARKER) != -1:
                temp_members.append(member)
                segments = folder_segments[:]
                segments.append(member)
                if temp_filesystem.isFolder(segments):
                    temp_filesystem.deleteFolder(segments, recursive=True)
                else:
                    temp_filesystem.deleteFile(segments)

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
                u'SELECT PeakWorkingSetSize '
                u'FROM Win32_Process '
                u'WHERE Handle=%d' % os.getpid())
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
            message = u'%s not in %s.' % (repr(source), repr(target))
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
                "Expecting type %s, but got %s. %s" % (
                    expected_type, type(value), msg))

    def assertRaises(self, exception_class, callback=None, *args, **kwargs):
        """
        Overwrites the stdlib call to allow non-context usage.
        """
        super_assertRaises = super(ChevahTestCase, self).assertRaises
        if callback is None:
            return super_assertRaises(exception_class)

        with super_assertRaises(exception_class) as context:
            callback(*args, **kwargs)

        return context.exception


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
            username=cls.os_user.name, token=cls.os_user.token)

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
        from chevah.compat.testing import TEST_ACCOUNT_GROUP
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
