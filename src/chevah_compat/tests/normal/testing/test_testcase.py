# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for ChevahTestCase.
"""

import os
import sys
import time

from twisted.internet import defer, reactor, threads
from twisted.internet.task import Clock

from chevah_compat import process_capabilities
from chevah_compat.testing import ChevahTestCase, conditionals, mk


class Dummy:
    """
    Dummy class to help with testing.
    """

    _value = mk.string()

    def method(self):
        return self._value


class TestTwistedTestCase(ChevahTestCase):
    """
    General tests for TwistedTestCase as part of ChevahTestCase.
    """

    def test_runDeferred_non_deferred(self):
        """
        An assertion error is raised when runDeferred is called for
        something which is not an deferred.
        Ex. a delayedCall
        """
        scheduler = Clock()
        delayed_call = scheduler.callLater(0, lambda: None)  # pragma: no cover

        with self.assertRaises(AssertionError) as context:
            self._runDeferred(delayed_call)

        self.assertEqual('This is not a deferred.', context.exception.args[0])

    def test_runDeferred_timeout_custom(self):
        """
        runDeferred will execute the reactor and raise an exception
        if deferred got no result after the timeout.
        """
        deferred = defer.Deferred()

        with self.assertRaises(AssertionError) as context:
            self._runDeferred(deferred, timeout=0)

        self.assertEqual(
            'Deferred took more than 0 to execute.',
            context.exception.args[0],
        )

        # Restore order messing with internal timeout state in
        # previous state.
        self._reactor_timeout_failure = None

    def test_runDeferred_timeout_default(self):
        """
        It will execute the reactor and raise an exception if the
        default timeout passes and the deferred is not completed.
        """
        self.DEFERRED_TIMEOUT = 0
        deferred = defer.Deferred()

        with self.assertRaises(AssertionError) as context:
            self._runDeferred(deferred)

        self.assertEqual(
            'Deferred took more than 0 to execute.',
            context.exception.args[0],
        )

        # Restore order messing with internal timeout state in
        # previous state.
        self._reactor_timeout_failure = None

    def test_runDeferred_non_recursive(self):
        """
        runDeferred will execute the reactor and wait for deferred
        tu return a result.
        """
        deferred = defer.Deferred()
        reactor.callLater(0.001, lambda d: d.callback('ok'), deferred)

        self._runDeferred(deferred, timeout=0.3)

        self.assertEqual('ok', deferred.result)

    def test_runDeferred_callbacks_list(self):
        """
        runDeferred will execute the reactor and wait for deferred
        to return a non-deferred result from the deferreds callbacks list.
        """
        # We use an uncalled deferred, to make sure that callbacks are not
        # executed when we call addCallback.
        deferred = defer.Deferred()
        two_deferred = defer.Deferred()
        three_deferred = defer.Deferred()
        four_deferred = defer.Deferred()
        deferred.addCallback(lambda result: two_deferred)
        deferred.addCallback(lambda result: three_deferred)
        deferred.addCallback(lambda result: four_deferred)
        reactor.callLater(0.001, lambda d: d.callback('one'), deferred)
        reactor.callLater(0.001, lambda d: d.callback('two'), two_deferred)
        reactor.callLater(0.002, lambda d: d.callback('three'), three_deferred)
        reactor.callLater(0.003, lambda d: d.callback('four'), four_deferred)

        self._runDeferred(deferred, timeout=0.3)

        self.assertEqual('four', deferred.result)

    def test_runDeferred_cleanup(self):
        """
        runDeferred will execute the reactor and will leave the reactor
        stopped.
        """
        deferred = defer.succeed(True)

        # Make sure we have a threadpool before calling runDeferred.
        threadpool = reactor.getThreadPool()
        self.assertIsNotNone(threadpool)
        self.assertIsNotNone(reactor.threadpool)

        self._runDeferred(deferred, timeout=0.3)

        self.assertIsTrue(deferred.result)
        self.assertIsNone(reactor.threadpool)
        self.assertFalse(reactor.running)

    def test_runDeferred_prevent_stop(self):
        """
        When called with `prevent_stop=True` runDeferred will not
        stop the reactor at exit.

        In this way, threadpool and other shared reactor resources can be
        reused between multiple calls of runDeferred.
        """
        deferred = defer.succeed(True)
        # Force the reactor to create an internal threadpool, in
        # case it was removed by previous calls.
        initial_pool = reactor.getThreadPool()

        with self.patchObject(reactor, 'stop') as mock_stop:
            self._runDeferred(deferred, timeout=0.3, prevent_stop=True)

        # reactor.stop is not called
        self.assertIsFalse(mock_stop.called)
        self.assertIsTrue(reactor._started)
        self.assertIsTrue(deferred.result)
        self.assertIsNotNone(reactor.threadpool)
        self.assertIs(initial_pool, reactor.threadpool)

        # Run again and we should still have the same pool.
        with self.patchObject(reactor, 'startRunning') as mock_start:
            self._runDeferred(
                defer.succeed(True),
                timeout=0.3,
                prevent_stop=True,
            )

        # reactor.start() is not called if reactor was not previously
        # stopped.
        self.assertIsFalse(mock_start.called)
        self.assertIs(initial_pool, reactor.threadpool)

        # Run again but this time call reactor.stop.
        self._runDeferred(defer.succeed(True), timeout=0.3, prevent_stop=False)

        self.assertIsFalse(reactor._started)
        self.assertIsNone(reactor.threadpool)

    def test_assertNoResult_good(self):
        """
        assertNoResult will not fail if deferred has no result yet.
        """
        deferred = defer.Deferred()
        self.assertNoResult(deferred)

    def test_assertNoResult_fail(self):
        """
        assertNoResult will fail if deferred has a result.
        """
        deferred = defer.Deferred()
        deferred.callback(None)

        with self.assertRaises(AssertionError):
            self.assertNoResult(deferred)

    def test_successResultOf_ok(self):
        """
        successResultOf will not fail if deferred has a result.
        """
        value = object()
        deferred = defer.succeed(value)

        result = self.successResultOf(deferred)

        self.assertEqual(value, result)

    def test_successResultOf_no_result(self):
        """
        successResultOf will fail if deferred has no result.
        """
        deferred = defer.Deferred()

        with self.assertRaises(AssertionError):
            self.successResultOf(deferred)

    def test_successResultOf_failure(self):
        """
        successResultOf will fail if deferred has a failure.
        """
        deferred = defer.fail(AssertionError())

        with self.assertRaises(AssertionError):
            self.successResultOf(deferred)

    def test_failureResultOf_good_any(self):
        """
        failureResultOf will return the failure.
        """
        error = AssertionError('bla')
        deferred = defer.fail(error)

        failure = self.failureResultOf(deferred)

        self.assertEqual(error, failure.value)

    def test_failureResultOf_good_type(self):
        """
        failureResultOf will return the failure of a specific type.
        """
        error = NotImplementedError('bla')
        deferred = defer.fail(error)

        failure = self.failureResultOf(deferred, NotImplementedError)

        self.assertEqual(error, failure.value)

    def test_failureResultOf_bad_type(self):
        """
        failureResultOf will fail if failure is not of the specified type.
        """
        error = NotImplementedError('bla')
        deferred = defer.fail(error)

        with self.assertRaises(AssertionError):
            self.failureResultOf(deferred, SystemExit)

    def test_failureResultOf_no_result(self):
        """
        failureResultOf will fail if deferred got no result.
        """
        deferred = defer.Deferred()

        with self.assertRaises(AssertionError):
            self.failureResultOf(deferred)

    def test_failureResultOf_no_failure(self):
        """
        failureResultOf will fail if deferred is not a failure.
        """
        deferred = defer.succeed(None)

        with self.assertRaises(AssertionError):
            self.failureResultOf(deferred)

    def test_executeReactor_delayedCalls_chained(self):
        """
        It will wait for all delayed calls to execute, included delayed
        which are later created by another delayed call.
        """
        self.called = False

        def last_call():
            self.called = True

        reactor.callLater(0.01, lambda: reactor.callLater(0.01, last_call))

        self.executeReactor()

        self.assertTrue(self.called)

    def test_executeReactor_threadpool(self):
        """
        It will wait for all workers from threadpool.
        """
        self.called = False

        def last_call():
            time.sleep(0.1)
            self.called = True

        deferred = threads.deferToThread(last_call)

        self.executeReactor()
        self.assertTrue(self.called)
        self.assertTrue(deferred.called)

    def test_executeReactor_timeout_value(self):
        """
        It will use the requested timeout value for executing the reactor.
        """
        self.called = False

        def last_call():
            self.called = True

        reactor.callLater(1.5, last_call)

        self.executeReactor(timeout=2)

        self.assertTrue(self.called)

    def test_assertReactorIsClean_excepted_deferred(self):
        """
        Will raise an error if a delayed call is still on the reactor queue.
        """

        def much_later():  # pragma: no cover
            """
            This is here to have a name.
            """

        delayed_call = reactor.callLater(10, much_later)

        with self.assertRaises(AssertionError) as context:
            self._assertReactorIsClean()

        self.assertEqual(
            'Reactor is not clean. delayed calls: much_later',
            context.exception.args[0],
        )
        # Cancel and remove it so that the general test will not fail.
        delayed_call.cancel()
        self.executeReactor()

    def test_assertReactorIsClean_excepted_delayed_calls(self):
        """
        Will not raise an error if delayed call should be ignored.
        """

        def much_later():  # pragma: no cover
            """
            This is here to have a name.
            """

        self.EXCEPTED_DELAYED_CALLS = ['much_later']

        delayed_call = reactor.callLater(10, much_later)

        self._assertReactorIsClean()
        # Cancel and remove it so that other tests will not fail.
        delayed_call.cancel()
        self.executeReactor()

    def test_assertReactorIsClean_threads(self):
        """
        It will cancel any pending jobs for the threads.
        """

        def last_call():  # pragma: no cover
            # This is added to the thread queue, but does not has the time
            # to be executed as our assertion will remove it from the queue.
            time.sleep(1)

        threads.deferToThread(last_call)

        with self.assertRaises(AssertionError) as context:
            self._assertReactorIsClean()

        self.assertContains(
            'Reactor is not clean. threadpoool queue:',
            context.exception.args[0],
        )

        # It will auto-clean the pool, so calling it again will not fail.
        self._assertReactorIsClean()

    def test_cleanReactor_delayed_calls_all_active(self):
        """
        It will cancel any delayed calls in the reactor queue.
        """
        reactor.callLater(1, self.ignoreFailure)
        reactor.callLater(2, self.ignoreFailure)
        self.assertIsNotEmpty(reactor.getDelayedCalls())

        self._cleanReactor()

        self.assertIsEmpty(reactor.getDelayedCalls())

    def test_cleanReactor_delayed_calls_some_called(self):
        """
        It will not break if a call is already called and will continue
        canceling the .
        """
        delayed_call_1 = reactor.callLater(1, self.ignoreFailure)
        delayed_call_2 = reactor.callLater(2, self.ignoreFailure)
        # Fake that deferred was called and make sure it is first in the list
        # so that we can can check that the operation will continue.
        delayed_call_1.called = True
        self.assertEqual(
            [delayed_call_1, delayed_call_2],
            reactor.getDelayedCalls(),
        )

        self._cleanReactor()

        self.assertTrue(delayed_call_2.cancelled)
        # Since we are messing with the reactor, we are leaving it in an
        # inconsistent state as no called delayed call should be part of the
        # list... since when called, the delayed called is removed right
        # away, yet we are not removing it but only faking its call.
        delayed_call_1.called = False
        self._cleanReactor()
        self.assertIsEmpty(reactor.getDelayedCalls())

    def test_executeDelayedCalls(self):
        """
        It will wait for delayed calls to be executed and then leave the
        reactor opened.
        """
        results = []
        reactor.callLater(0.1, lambda x: results.append(x), True)
        # Make sure reactor is stopped at the end of the test.
        self.addCleanup(self.executeReactor)

        self.executeDelayedCalls()

        self.assertEqual([True], results)
        self.assertTrue(reactor._started)

    def test_executeDelayedCalls_with_timeout(self):
        """
        When the delayed calls are not ready after timeout, it will fail.
        """
        results = []
        reactor.callLater(0.2, lambda x: results.append(x), True)
        # Make sure reactor is stopped at the end of the test.
        self.addCleanup(self.executeReactor)

        with self.assertRaises(AssertionError) as context:
            self.executeDelayedCalls(timeout=0.1)

        self.assertEqual(
            'executeDelayedCalls took more than 0.1',
            context.exception.args[0],
        )
        # Delayed call not called and reactor is stopped.
        self.assertEqual([], results)
        self.assertFalse(reactor._started)

    def test_executeReactorUntil(self):
        """
        It will execute the reactor and leave it open.
        """
        results = []
        reactor.callLater(0.1, lambda x: results.append(x), True)
        call_2 = reactor.callLater(  # pragma: no cover
            0.2,
            lambda x: results.append(x),
            False,
        )
        # Make sure call is not already called.
        self.assertEqual([], results)

        # Wait until first callback is called.
        self.executeReactorUntil(
            lambda _: results == [True],
            prevent_stop=False,
        )

        self.assertEqual([True], results)
        # The second call is not called and we need to cancel it, otherwise
        # the reactor will not be clean.
        call_2.cancel()

    def test_executeReactorUntil_timeout(self):
        """
        It will execute the reactor and leave it open.
        """
        results = []
        reactor.callLater(0.1, lambda x: results.append(x), True)
        # Make sure call is not already called.
        self.assertEqual([], results)

        # Wait until first callback is called.
        self.executeReactorUntil(
            lambda _: False,
            prevent_stop=False,
            timeout=0.2,
        )

        # The reactor was spin.
        self.assertEqual([True], results)
        self.assertEqual(
            'Reactor took more than 0.20 seconds to execute.',
            self._reactor_timeout_failure.args[0],
        )
        # Ignore this error so that it will not be triggered in tearDown.
        self._reactor_timeout_failure = None

    def test_iterateReactor(self):
        """
        It will execute the reactor and leave it open.
        """
        results = []
        reactor.callLater(0, lambda x: results.append(x), True)
        # Make sure reactor is stopped at the end of the test.
        self.addCleanup(self.executeReactor)
        # Make sure call is not already called.
        self.assertEqual([], results)

        self.iterateReactor()

        self.assertEqual([True], results)
        self.assertTrue(reactor._started)

    def test_iterateReactorWithStop(self):
        """
        It will execute the reactor and stop it.
        """
        results = []
        reactor.callLater(0, lambda x: results.append(x), True)
        # Make sure call is not already called.
        self.assertEqual([], results)

        self.iterateReactorWithStop()

        self.assertEqual([True], results)
        self.assertFalse(reactor._started)

    def test_iterateReactorForSeconds(self):
        """
        It will execute the reactor for x seconds and leave it open.
        """
        results = []
        reactor.callLater(0.1, lambda x: results.append(x), True)
        # Make sure call is not already called.
        self.assertEqual([], results)
        # Make sure reactor is stopped at the end of the test.
        self.addCleanup(self.executeReactor)

        self.iterateReactorForSeconds(0.2)

        self.assertEqual([True], results)
        self.assertFalse(reactor._started)


class TestTwistedTimeoutTestCase(ChevahTestCase):
    """
    Test for the default timeout.
    """

    DEFERRED_TIMEOUT = 1.5

    def test_executeReactor_timeout_default(self):
        """
        It will use the default timeout value defined on the test case.
        """
        self.called = False

        def last_call():
            self.called = True

        reactor.callLater(1.25, last_call)

        self.executeReactor()

        self.assertTrue(self.called)


class TestChevahTestCase(ChevahTestCase):
    """
    General tests for ChevahTestCase.
    """

    def test_cleanTemporaryFolder_empty(self):
        """
        Empty list is returned if temporary folder does not contain test
        files for folders.
        """
        result = self.cleanTemporaryFolder()

        self.assertIsEmpty(result)

    def test_cleanTemporaryFolder_content(self):
        """
        The list of members is returned if temporary folder contains test
        files for folders.

        Only root members are returned and folders are removed recursively.
        """
        file1 = mk.fs.createFileInTemp()
        folder1 = mk.fs.createFolderInTemp()
        folder1_file2 = folder1[:]
        folder1_file2.append(mk.makeFilename())

        result = self.cleanTemporaryFolder()

        self.assertEqual(2, len(result))
        self.assertContains(file1[-1], result)
        self.assertContains(folder1[-1], result)

    def test_patch(self):
        """
        It can be used for patching classes.
        """
        value = mk.string()

        with self.patch(
            'chevah_compat.tests.normal.testing.test_testcase.Dummy.method',
            return_value=value,
        ):
            instance = Dummy()
            self.assertEqual(value, instance.method())

        # After exiting the context, the value is restored.
        instance = Dummy()
        self.assertEqual(Dummy._value, instance.method())

    def test_patchObject(self):
        """
        It can be used for patching an instance of an object.
        """
        value = mk.string()
        one_instance = Dummy()

        with self.patchObject(one_instance, 'method', return_value=value):
            self.assertEqual(value, one_instance.method())

            # All other instances are not affected.
            new_instance = Dummy()
            self.assertEqual(Dummy._value, new_instance.method())

        # After exiting the context, the value is restored.
        self.assertEqual(Dummy._value, one_instance.method())

    def test_Mock(self):
        """
        It creates a generic mock object.
        """
        value = mk.string()

        mock = self.Mock(return_value=value)

        self.assertEqual(value, mock())

    def test_skipped_test(self):
        """
        Just a test to check that everything works ok with skipped tests
        in a normal testcase.
        """
        raise self.skipTest()

    @conditionals.skipOnCondition(lambda: False, 'Should not be skipped!!!')
    def test_skipOnCondition_call(self):
        """
        Run test when callback return False.
        """

    @conditionals.skipOnCondition(lambda: True, 'As expected.')
    def test_skipOnCondition_skip(self):
        """
        Skip test when callback return True.
        """
        raise AssertionError('Should not be called.')

    @conditionals.onOSFamily('posix')
    def test_onOSFamily_posix(self):
        """
        Run test only on posix.
        """
        if os.name != 'posix':
            raise AssertionError('This should be called only on posix.')

    @conditionals.onOSFamily('nt')
    def test_onOSFamily_nt(self):
        """
        Run test only on NT. This is the complement of previous test.
        """
        if os.name != 'nt':
            raise AssertionError('This should be called only on NT.')

    @conditionals.onOSName('linux')
    def test_onOSName_linux(self):
        """
        Run test only on Linux.
        """
        if not sys.platform.startswith('linux'):
            raise AssertionError('This should be called only on Linux.')

    @conditionals.onOSName(['linux', 'aix'])
    def test_onOSName_linux_aix(self):
        """
        Run test only on Linux and AIX.
        """
        if not sys.platform.startswith('linux') and not sys.platform.startswith(
            'aix',
        ):
            raise AssertionError('This should be called only on Linux and AIX.')

    @conditionals.onCapability('impersonate_local_account', True)
    def test_onCapability(self):
        """
        Run test only when impersonate_local_account is True.
        """
        # We ignore the statements in this code from coverage,
        # but we don't ignore the whole test to make sure that it is
        # executed.
        can_impersonate = (
            process_capabilities.impersonate_local_account
        )  # pragma: no cover
        if can_impersonate is not True:  # pragma: no cover
            raise AssertionError(
                'This should be called only when impersonate_local_account '
                'is True.',
            )

    @conditionals.onAdminPrivileges(True)
    def test_onAdminPrivileges_present(self):
        """
        Run test only on machines that execute the tests with administrator
        privileges.
        """
        if self.os_version in ['nt-5.1', 'nt-5.2']:
            raise AssertionError(
                'Windows XP and 2003 BS does not run as administrator',
            )

        if self.ci_name in [self.CI.TRAVIS, self.CI.GITHUB]:
            raise AssertionError(
                'Travis and GitHub does not run as administrator',
            )

    @conditionals.onAdminPrivileges(False)
    def test_onAdminPrivileges_missing(self):
        """
        Run test on build slaves that do not have administrator privileges.
        """
        if (
            self.TEST_LANGUAGE == 'FR'
            or self.os_name
            or self.ci_name not in [self.CI.BUILDBOT, self.CI.LOCAL]
        ):
            # Not available on Windows XP and 2003 and non-buildbot runs.
            return

        raise AssertionError(
            f'"{self.hostname}" is running with administrator privileges',
        )

    def test_cleanup_test_segments_file(self):
        """
        When self.test_segments is defined it will be automatically
        removed.
        """
        self.test_segments = mk.fs.createFileInTemp()

    def test_cleanup_test_segments_folder(self):
        """
        When self.test_segments is defined it will be automatically
        removed, even when is a folder with content.
        """
        self.test_segments = mk.fs.createFolderInTemp()
        child_segments = self.test_segments[:]
        child_segments.append(mk.makeFilename())
        mk.fs.createFolder(child_segments)

    @conditionals.onCapability('symbolic_link', True)
    def test_cleanup_test_segments_link(self):
        """
        When self.test_segments is defined it will be automatically
        removed, even when it is a symbolic link.
        """
        _, self.test_segments = mk.fs.makePathInTemp(
            prefix='test_cleanup_test_segments_link',
        )

        mk.fs.makeLink(
            target_segments=mk.fs.temp_segments,
            link_segments=self.test_segments,
        )

    def test_assertIsInstance(self):
        """
        Is has the argument in the inverse order of stdlib version.
        """
        self.assertIsInstance(object, object())

    def test_assertIn(self):
        """
        Is has the argument in the inverse order of stdlib version.
        """
        self.assertIn({1, 'a', 'b'}, 'a')

    def test_assertRaises(self):
        """
        It can be used as a simple call, not as context, directly returning
        the exception.
        """

        def some_call(argument):
            raise RuntimeError(f'error-marker-{argument}')

        exception = self.assertRaises(RuntimeError, some_call, 'more')

        self.assertEqual('error-marker-more', exception.args[0])

    def test_stacked_cleanup(self):
        """
        It supports calling cleanup based on multiple stacks.
        """
        # Tests are based on a list and append to detect accidental duplicate
        # calls of the same cleanup.
        self.base_stack_called = []
        self.medium_stack_called = []
        self.top_stack_called = []

        # Not lambda to make it easy to debug.
        def base_cleanup():
            self.base_stack_called.append(True)

        def medium_cleanup():
            self.medium_stack_called.append(True)

        def top_cleanup():
            self.top_stack_called.append(True)

        self.addCleanup(base_cleanup)

        self.enterCleanup()
        self.addCleanup(medium_cleanup)

        # Can also be used as context manager.
        with self.stackedCleanup():
            self.addCleanup(top_cleanup)

            # Nothing called so far.
            self.assertEqual([], self.base_stack_called)
            self.assertEqual([], self.medium_stack_called)
            self.assertEqual([], self.top_stack_called)

        # Exit top cleanup stack is implicit as part of the context manager.
        self.assertEqual([], self.base_stack_called)
        self.assertEqual([], self.medium_stack_called)
        self.assertEqual([True], self.top_stack_called)

        # Exit medium cleanup stack.
        self.exitCleanup()
        self.assertEqual([], self.base_stack_called)
        self.assertEqual([True], self.medium_stack_called)
        self.assertEqual([True], self.top_stack_called)

        # Call base cleanup.
        self.callCleanup()
        self.assertEqual([True], self.base_stack_called)
        self.assertEqual([True], self.medium_stack_called)
        self.assertEqual([True], self.top_stack_called)


@conditionals.onOSFamily('posix')
class TestClassConditionalsPosix(ChevahTestCase):
    """
    Conditionals also work on classes.
    """

    def test_onOSFamily_posix(self):
        """
        Run test only on posix.
        """
        if os.name != 'posix':
            raise AssertionError('This should be called only on posix.')


@conditionals.onOSFamily('nt')
class TestClassConditionalsNT(ChevahTestCase):
    """
    This is the complement of the previous tests.
    """

    def test_onOSFamily(self):
        """
        Run test only on nt.
        """
        if os.name != 'nt':
            raise AssertionError('This should be called only on nt.')


class TestChevahTestCaseSkipSetup(ChevahTestCase):
    """
    Test skipped test at setup level.
    """

    def setUp(self):
        """
        Skip the test, after initializing parent.

        This will prevent calling of tearDown.
        """
        super().setUp()

        raise self.skipTest()

    def tearDown(self):
        raise AssertionError('Should not be called.')

    def test_skipped_test(self):
        """
        Just a test to check that everything works ok with skipped tests.
        """
        raise AssertionError('Should not be called')


class TestChevahTestCaseAddCleanup(ChevahTestCase):
    """
    Test case for checking addCleanup.
    """

    def setUp(self):
        super().setUp()
        self.cleanup_call_count = 0

    def tearDown(self):
        self.assertEqual(0, self.cleanup_call_count)
        super().tearDown()
        self.assertEqual(2, self.cleanup_call_count)

    def cleanUpLast(self):
        self.assertEqual(1, self.cleanup_call_count)
        self.cleanup_call_count += 1

    def cleanUpFirst(self):
        self.assertEqual(0, self.cleanup_call_count)
        self.cleanup_call_count += 1

    def test_addCleanup(self):
        """
        Will call the cleanup method at tearDown in the revere order
        in which they were added.
        """
        self.addCleanup(self.cleanUpLast)
        self.addCleanup(self.cleanUpFirst)

        self.assertEqual(0, self.cleanup_call_count)


class TestChevahTestCaseCallCleanup(ChevahTestCase):
    """
    Test case for checking callCleanup.
    """

    def setUp(self):
        super().setUp()
        self.cleanup_call_count = 0

    def tearDown(self):
        self.assertEqual(1, self.cleanup_call_count)
        super().tearDown()
        self.assertEqual(1, self.cleanup_call_count)

    def cleanUp(self):
        self.cleanup_call_count += 1

    def test_callCleanup(self):
        """
        Will call registered cleanup methods and will not be called again at
        tearDown or at any other time it is called.
        """
        self.addCleanup(self.cleanUp)

        self.assertEqual(0, self.cleanup_call_count)

        self.callCleanup()

        # Check that callback is called.
        self.assertEqual(1, self.cleanup_call_count)

        # Calling again produce no changes.
        self.callCleanup()
        self.assertEqual(1, self.cleanup_call_count)
