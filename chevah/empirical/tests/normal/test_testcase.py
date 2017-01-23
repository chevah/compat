# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for ChevahTestCase.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import object
import os
import sys
import time

from twisted.internet import defer, reactor, threads
from twisted.internet.task import Clock
from twisted.python.failure import Failure

from chevah.compat import process_capabilities
from chevah.empirical import conditionals, EmpiricalTestCase, mk


class Dummy(object):
    """
    Dummy class to help with testing.
    """
    _value = mk.string()

    def method(self):
        return self._value


class ErrorWithID(Exception):
    """
    An error that provides an id to help with testing.
    """
    def __init__(self, id):
        super(ErrorWithID, self).__init__()
        self._id = id

    @property
    def id(self):
        """
        Return error id.
        """
        return self._id


class TestTwistedTestCase(EmpiricalTestCase):
    """
    General tests for TwistedTestCase as part of EmpiricalTestCase.
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
            self.runDeferred(delayed_call)

        self.assertEqual(
            'This is not a deferred.', context.exception.args[0])

    def test_runDeferred_timeout(self):
        """
        runDeferred will execute the reactor and raise a timeout
        if deferred got no result after the timeout.
        """
        deferred = defer.Deferred()

        with self.assertRaises(AssertionError) as context:
            self.runDeferred(deferred, timeout=0)

        self.assertEqual(
            'Deferred took more than 0 to execute.',
            context.exception.args[0]
            )

        # Restore order order messing with internal timeout state in
        # previous state.
        self._reactor_timeout_failure = None

    def test_runDeferred_non_recursive(self):
        """
        runDeferred will execute the reactor and wait for deferred
        tu return a result.
        """
        deferred = defer.Deferred()
        reactor.callLater(0.001, lambda d: d.callback('ok'), deferred)

        self.runDeferred(deferred, timeout=0.3)

        self.assertEqual('ok', deferred.result)

    def test_runDeferred_callbacks_list(self):
        """
        runDeferred will execute the reactor and wait for deferred
        to return a non-deferred result from the deferrers callbacks list.
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
        reactor.callLater(
            0.002, lambda d: d.callback('three'), three_deferred)
        reactor.callLater(0.003, lambda d: d.callback('four'), four_deferred)

        self.runDeferred(deferred, timeout=0.3)

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

        self.runDeferred(deferred, timeout=0.3)

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
            self.runDeferred(deferred, timeout=0.3, prevent_stop=True)

        # reactor.stop() is not called
        self.assertIsFalse(mock_stop.called)
        self.assertIsTrue(reactor._started)
        self.assertIsTrue(deferred.result)
        self.assertIsNotNone(reactor.threadpool)
        self.assertIs(initial_pool, reactor.threadpool)

        # Run again and we should still have the same pool.
        with self.patchObject(reactor, 'startRunning') as mock_start:
            self.runDeferred(
                defer.succeed(True), timeout=0.3, prevent_stop=True)

        # reactor.start() is not called if reactor was not previously
        # stopped.
        self.assertIsFalse(mock_start.called)
        self.assertIs(initial_pool, reactor.threadpool)

        # Run again but this time call reactor.stop.
        self.runDeferred(
            defer.succeed(True), timeout=0.3, prevent_stop=False)

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
        error = AssertionError(u'bla')
        deferred = defer.fail(error)

        failure = self.failureResultOf(deferred)

        self.assertEqual(error, failure.value)

    def test_failureResultOf_good_type(self):
        """
        failureResultOf will return the failure of a specific type.
        """
        error = NotImplementedError(u'bla')
        deferred = defer.fail(error)

        failure = self.failureResultOf(deferred, NotImplementedError)

        self.assertEqual(error, failure.value)

    def test_failureResultOf_bad_type(self):
        """
        failureResultOf will fail if failure is not of the specified type.
        """
        error = NotImplementedError(u'bla')
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
            self.assertReactorIsClean()

        self.assertEqual(
            u'Reactor is not clean. delayed calls: much_later',
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

        self.assertReactorIsClean()
        # Cancel and remove it so that other tests will not fail.
        delayed_call.cancel()
        self.executeReactor()


class TestEmpiricalTestCase(EmpiricalTestCase):
    """
    General tests for EmpiricalTestCase.
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

    def test_assertTempIsClean_clean_temp(self):
        """
        No error is raised if temp folder is clean.
        """
        self.assertTempIsClean()

    def test_assertTempIsClean_dirty(self):
        """
        If temp is not clean an error is raised and then temp folders
        is cleaned.
        """
        temp_segments = mk.fs.createFileInTemp()

        with self.assertRaises(AssertionError) as context:
            self.assertTempIsClean()

        message = context.exception.args[0].decode('utf-8')
        self.assertStartsWith(u'Temporary folder is not clean.', message)
        self.assertContains(temp_segments[-1], message)

        self.assertFalse(mk.fs.exists(temp_segments))

    def test_patch(self):
        """
        It can be used for patching classes.
        """
        value = mk.string()

        with self.patch(
            'chevah.empirical.tests.normal.test_testcase.Dummy.method',
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

        with self.patchObject(
                one_instance, 'method', return_value=value):
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

    def test_listenPort(self):
        """
        It can be used for listening a dummy connection on a port and address.
        """
        address = '127.0.0.1'
        port = 10000

        with self.listenPort(address, port):

            self.assertIsListening(address, port)

    def test_listenPort_on_loopback_alias(self):
        """
        Integration test to check that we can listen on loopback alias.

        This is a system test, but socket operations are light.
        """
        if self.os_name in ['aix', 'solaris', 'osx']:
            # On AIX and probably on other Unixes we can only bind on
            # existing fixed IP addressed like 127.0.0.1.
            raise self.skipTest()

        # This is just a test to make sure that the server can listen to
        # 127.0.0.10 as this IP is used in other tests.
        address = '127.0.0.10'
        port = 10070

        with self.listenPort(address, port):

            self.assertIsListening(address, port)

    def check_assertWorkingFolderIsClean(self, content):
        """
        Common tests for assertWorkingFolderIsClean.
        """

        with self.assertRaises(AssertionError) as context:
            self.assertWorkingFolderIsClean()

        message = context.exception.args[0].decode('utf-8')
        for member in content:
            self.assertContains(member, message)

        # Calling it again will not raise any error since the folder is clean.
        self.assertWorkingFolderIsClean()

    def test_assertWorkingFolderIsClean_with_folder(self):
        """
        An error is raised if current working folder contains a temporary
        folder and folder is cleaned.
        """
        # Our compat filesystem API does not support creating files in
        # current working directory so we use direct API call to OS.
        name = mk.string()
        os.mkdir(mk.fs.getEncodedPath(name))

        self.check_assertWorkingFolderIsClean([name])

    def test_assertWorkingFolderIsClean_with_file(self):
        """
        An error is raised if current working folder contains a temporary
        file and file is cleaned.
        """
        name = mk.string()
        open(mk.fs.getEncodedPath(name), 'a').close()

        self.check_assertWorkingFolderIsClean([name])

    def test_assertWorkingFolderIsClean_with_file_and_folder(self):
        """
        An error is raised if current working folder contains a temporary
        folder and file, and folder and folder is cleaned.
        """
        file_name = mk.string()
        folder_name = mk.string()
        open(mk.fs.getEncodedPath(file_name), 'a').close()
        os.mkdir(mk.fs.getEncodedPath(folder_name))

        self.check_assertWorkingFolderIsClean([file_name, folder_name])

    def test_assertFailureID_unicode_id(self):
        """
        Can be called with unicode failure id.
        """
        failure = Failure(ErrorWithID(u'100'))

        self.assertFailureID(u'100', failure)

    def test_assertFailureID_non_unicode_id(self):
        """
        It will raise an error if the failure id is not unicode.
        """
        failure = Failure(ErrorWithID(100))

        with self.assertRaises(AssertionError):
            self.assertFailureID(100, failure)

        failure = Failure(ErrorWithID("100"))

        with self.assertRaises(AssertionError):
            self.assertFailureID("100", failure)

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

    @conditionals.onOSFamily('posiX')
    def test_onOSFamily_posix(self):
        """
        Run test only on posix.
        """
        if os.name != 'posix':
            raise AssertionError('This should be called only on posix.')

    @conditionals.onOSFamily('Nt')
    def test_onOSFamily_nt(self):
        """
        Run test only on NT. This is the complement of previous test.
        """
        if os.name != 'nt':
            raise AssertionError('This should be called only on NT.')

    @conditionals.onOSName('linuX')
    def test_onOSName_linux(self):
        """
        Run test only on Linux.
        """
        if not sys.platform.startswith('linux'):
            raise AssertionError('This should be called only on Linux.')

    @conditionals.onOSName(['Linux', 'aix'])
    def test_onOSName_linux_aix(self):
        """
        Run test only on Linux and AIX.
        """
        if (not sys.platform.startswith('linux') and
                not sys.platform.startswith('aix')):
            raise AssertionError(
                'This should be called only on Linux and AIX.')

    @conditionals.onCapability('impersonate_local_account', True)
    def test_onCapability(self):
        """
        Run test only when impersonate_local_account is True.
        """
        # We ignore the statements in this code from coverage,
        # but we don't ignore the whole test to make sure that it is
        # executed.
        can_impersonate = (
            process_capabilities.impersonate_local_account)  # pragma: no cover
        if can_impersonate is not True:  # pragma: no cover
            raise AssertionError(
                'This should be called only when impersonate_local_account '
                'is True.'
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
        _, self.test_segments = mk.fs.makePathInTemp()

        mk.fs.makeLink(
            target_segments=mk.fs.temp_segments,
            link_segments=self.test_segments,
            )

    def test_assertIsEmpty(self):
        """
        Raise an exception when not empty and otherwise does nothing.
        """
        self.assertIsEmpty(())
        self.assertIsEmpty([])
        self.assertIsEmpty('')
        self.assertIsEmpty(set())

        with self.assertRaises(AssertionError) as context:
            self.assertIsEmpty((1, 2))

        self.assertEqual(
            'Iterable is not empty.\n(1, 2).', context.exception.args[0])


@conditionals.onOSFamily('posiX')
class TestClassConditionalsPosix(EmpiricalTestCase):
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
class TestClassConditionalsNT(EmpiricalTestCase):
    """
    This is the complement of the previous tests.
    """
    def test_onOSFamily(self):
        """
        Run test only on nt.
        """
        if os.name != 'nt':
            raise AssertionError('This should be called only on nt.')


class TestEmpiricalTestCaseSkipSetup(EmpiricalTestCase):
    """
    Test skipped test at setup level.
    """

    def setUp(self):
        """
        Skip the test, after initializing parent.

        This will prevent calling of tearDown.
        """
        super(TestEmpiricalTestCaseSkipSetup, self).setUp()

        raise self.skipTest()

    def tearDown(self):
        raise AssertionError('Should not be called.')

    def test_skipped_test(self):
        """
        Just a test to check that everything works ok with skipped tests.
        """
        raise AssertionError('Should not be called')


class TestEmpiricalTestCaseAddCleanup(EmpiricalTestCase):
    """
    Test case for checking addCleanup.
    """

    def setUp(self):
        super(TestEmpiricalTestCaseAddCleanup, self).setUp()
        self.cleanup_call_count = 0

    def tearDown(self):
        self.assertEqual(0, self.cleanup_call_count)
        super(TestEmpiricalTestCaseAddCleanup, self).tearDown()
        self.assertEqual(1, self.cleanup_call_count)

    def cleanUp(self):
        self.cleanup_call_count += 1

    def test_addCleanup(self):
        """
        Will be called at tearDown.
        """
        self.addCleanup(self.cleanUp)

        self.assertEqual(0, self.cleanup_call_count)


class TestEmpiricalTestCaseCallCleanup(EmpiricalTestCase):
    """
    Test case for checking callCleanup.
    """

    def setUp(self):
        super(TestEmpiricalTestCaseCallCleanup, self).setUp()
        self.cleanup_call_count = 0

    def tearDown(self):
        self.assertEqual(1, self.cleanup_call_count)
        super(TestEmpiricalTestCaseCallCleanup, self).tearDown()
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
