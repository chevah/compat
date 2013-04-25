# -*- coding: utf-8 -*-
# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Unit tests for Windows NT service functionality.
"""

from __future__ import with_statement
import os

from chevah.compat.nt_service import ChevahNTService
from chevah.compat.testing import CompatTestCase
from chevah.compat.testing import manufacture as mk


class DummyChevahNTService(ChevahNTService):
    _win32serviceutil = mk.makeMock()
    _servicemanager = mk.makeMock()
    initialize = mk.makeMock()


class FailChevahNTService(ChevahNTService):
    _win32serviceutil = mk.makeMock()
    _servicemanager = mk.makeMock()
    ReportServiceStatus = mk.makeMock()
    start = mk.makeMock()
    stop = mk.makeMock()
    info = mk.makeMock()
    error = mk.makeMock()
    SvcStop = mk.makeMock()

    def initialize_fail(self):
        raise AssertionError("Initialization error.")

    initialize = initialize_fail


class TestChevahNTService(CompatTestCase):
    """
    Unit tests for `ChevahNTService`.
    """

    def setUp(self):
        super(TestChevahNTService, self).setUp()

        if os.name != 'nt':
            raise self.skipTest("Only Windows platforms supported.")

        self.service = DummyChevahNTService()
        self.service.start = mk.makeMock()
        self.service.ReportServiceStatus = mk.makeMock()
        self.service.stop = mk.makeMock()
        self.service.info = mk.makeMock()
        self.service.error = mk.makeMock()

    def test_initialization_ok(self):
        """
        Service initialization test.
        """
        self.assertTrue(self.service.initialize.called)
        self.assertFalse(self.service.start.called)
        self.assertFalse(self.service.stop.called)

    def test_initialization_failure(self):
        """
        Service is stopped if initialization fails.
        """
        service = FailChevahNTService()

        self.assertTrue(service.error.called)
        self.assertTrue(service.SvcStop.called)

    def test_SvcDoRun(self):
        """
        `SvcDoRun` reports starting sequence initiated and calls specialized
        `start` method.
        """
        self.service.SvcDoRun()

        self.assertTrue(self.service.start.called)
        self.assertTrue(self.service.info.called)
        self.assertFalse(self.service.stop.called)

    def test_SvcDoRun_system_exit(self):
        """
        `SystemExit` exception is suppressed as it's regular way of signaling
        exit from the service process.
        """
        def start():
            raise SystemExit()

        self.service.start = start

        self.service.SvcDoRun()

        self.assertTrue(self.service.info.called)
        self.assertFalse(self.service.stop.called)
        self.assertFalse(self.service.error.called)

    def test_SvcStop(self):
        """
        `SvcStop` calls `stop` and reports that service has initiated stopping
        sequence.
        """
        import win32service

        self.service.SvcStop()

        self.service.ReportServiceStatus.assert_called_once_with(
            win32service.SERVICE_STOP_PENDING)
        self.assertTrue(self.service.stop.called)
        self.service.info.assert_called_once_with('Service stopped.')
