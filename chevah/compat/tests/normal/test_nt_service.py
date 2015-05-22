# Copyright (c) 2011 Adi Roiban.
"""
Unit tests for Windows NT Service.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import os

from chevah.compat.testing import CompatTestCase

if os.name == 'nt':
    import win32service
    from chevah.compat.nt_service import ChevahNTService
    # Silence the linter.
    ChevahNTService
else:
    # This is here to allow defining test classes.
    ChevahNTService = object


class dummy_win32serviceutil(object):
    """
    A dummy implementation for win32serviceutil package.
    """
    ServiceFramework = object


class dummy_servicemanager(object):
    """
    A dummy implementation of servicemanager.
    """
    def __init__(self):
        """
        Create fresh mocks.
        """
        self.RegisterServiceCtrlHandler = CompatTestCase.Mock()
        self.SetEventSourceName = CompatTestCase.Mock()

    def LogErrorMsg(self, text):
        """
        Raise an error.
        """
        raise AssertionError(text)


class ChevahNTServiceImplementation(ChevahNTService):
    """
    A simple implementation of ChevahNTService to help testing.
    """

    _svc_name_ = 'test service name'

    def __init__(self, *args, **kwargs):

        # Keep track of method calls.
        self._reported_service_status = []
        self._info_messages = []
        self._error_messages = []

        # Keep track of service state.
        self._started = False
        self._stopped = False
        self._running = False
        self._initialized = False

        # This is here to avoid triggering the real
        # win32serviceutil.ServiceFramework and create registers and other
        # side effects.
        self._win32serviceutil = dummy_win32serviceutil()
        self._service_manager = dummy_servicemanager()

        # Now that testing variables are set, we can call the low level
        # initialization.
        super(ChevahNTServiceImplementation, self).__init__(*args, **kwargs)

    def ReportServiceStatus(self, status):
        self._reported_service_status.append(status)

    def error(self, message):
        self._error_messages.append(message)

    def info(self, message):
        self._info_messages.append(message)

    def initialize(self):
        self._initialized = True

    def start(self):
        self._started = True
        self._running = True

    def stop(self):
        self._stopped = True
        self._running = False


class FailingInitializeChevahNTService(ChevahNTServiceImplementation):
    """
    An implementation of ChevahNTService which fails at initialization.
    """

    def initialize(self):
        raise AssertionError('test-initialize-error')


class FailingStartChevahNTService(ChevahNTServiceImplementation):
    """
    An implementation of ChevahNTService which fails at start.
    """

    def start(self):
        raise AssertionError('test-start-error')


class TestChevahNTService(CompatTestCase):
    """
    Unit tests for `ChevahNTService`.
    """

    @classmethod
    def setUpClass(cls):
        if os.name != 'nt':
            raise cls.skipTest()

    def test_initialize_ok(self):
        """
        On successful initialization the `initialize` method is called
        and service is not started yet.

        No error or information message is sent.
        """
        service = ChevahNTServiceImplementation((u'some-name',))

        self.assertTrue(service._initialized)
        self.assertFalse(service._running)
        self.assertFalse(service._started)
        self.assertFalse(service._stopped)
        self.assertIsEmpty(service._info_messages)
        self.assertIsEmpty(service._error_messages)

        sm = service._service_manager
        sm.RegisterServiceCtrlHandler.assert_called_once_with(
            u'some-name', service.ServiceCtrlHandlerEx, True)
        sm.SetEventSourceName.assert_called_once_with(u'some-name')

    def test_initialize_failure(self):
        """
        When service fails to initialize, service is stopped,
        a single error and a single informational message is reported.
        """
        service = FailingInitializeChevahNTService((u'some-name',))

        self.assertEqual(1, len(service._error_messages))
        self.assertContains(
            'Failed to initialize the service', service._error_messages[0])
        self.assertContains(
            'test-initialize-error', service._error_messages[0])

        self.assertTrue(service._stopped)

    def test_SvcDoRun_ok(self):
        """
        `SvcDoRun` reports starting sequence initiated and calls specialized
        `start` method.
        """
        service = ChevahNTServiceImplementation((u'some-name',))

        service.SvcDoRun()

        self.assertEqual(
            [win32service.SERVICE_START_PENDING,
                win32service.SERVICE_RUNNING],
            service._reported_service_status,
            )
        self.assertEqual([u'Service started.'], service._info_messages)
        self.assertTrue(service._started)
        self.assertTrue(service._running)
        self.assertFalse(service._stopped)

    def test_SvcDoRun_failure(self):
        """
        If there's a problem running the service `error` is called.
        """
        service = FailingStartChevahNTService((u'some-name',))

        service.SvcDoRun()

        self.assertEqual([u'Service started.'], service._info_messages)

    def test_SvcStop(self):
        """
        `SvcStop` calls `stop` and reports that service has initiated stopping
        sequence.
        """
        service = ChevahNTServiceImplementation((u'some-name',))

        service.SvcStop()

        self.assertEqual(
            [win32service.SERVICE_STOP_PENDING],
            service._reported_service_status,
            )
        self.assertTrue(service._stopped)
        self.assertEqual([u'Service stopped.'], service._info_messages)
