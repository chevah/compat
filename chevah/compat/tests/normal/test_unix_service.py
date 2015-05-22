# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Tests for Unix Daemon.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import os
import sys

from chevah.compat.exceptions import CompatError

from chevah.compat.helpers import NoOpContext
from chevah.compat.interfaces import IDaemon
from chevah.compat.testing import CompatTestCase, mk

if os.name == 'posix':
    from chevah.compat.unix_service import Daemon
    Daemon  # Shut up the linter.
else:
    Daemon = object


class DummyDaemonContext(NoOpContext):
    """
    A testing implementation of DaemonContext.
    """

    def __init__(self, stdin=None, stdout=None, stderr=None):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr


class DaemonImplementation(Daemon):
    """
    A testing implementation of IDaemon.
    """

    DaemonContext = DummyDaemonContext
    _daemon_context = None

    def __init__(self, *args, **kwargs):
        super(DaemonImplementation, self).__init__(*args, **kwargs)

        # The methods are mocked at init time to have different mocks for
        # each instance.
        self.getOpenFiles = CompatTestCase.Mock()
        self.getOpenFiles.return_value = [100, 123]
        self.onInitialize = CompatTestCase.Mock()
        self.onStart = CompatTestCase.Mock()
        self.onStop = CompatTestCase.Mock()


class TestDaemon(CompatTestCase):
    """
    Tests for Daemon.
    """

    @classmethod
    def setUpClass(cls):
        """
        Tests are supported only on Unix.
        """
        if os.name != 'posix':
            raise cls.skipTest()
        super(TestDaemon, cls).setUpClass()

    def getPIDPath(self):
        """
        Return path to a pid file.
        """
        (path, _) = mk.fs.makePathInTemp()
        return path

    def test_init(self):
        """
        Check initialization.
        """
        options = object()
        daemon = DaemonImplementation(options=options)

        self.assertProvides(IDaemon, daemon)
        self.assertEqual(options, daemon.options)
        self.assertIsFalse(daemon.preserve_standard_streams)
        self.assertIsTrue(daemon.detach_process)

    def test_launch_preserve_standard_streams(self):
        """
        When preserve_standard_streams is set, the new daemon will
        inherit the standard stream.
        """
        pid_path = self.getPIDPath()
        options = self.Bunch(pid=pid_path)
        daemon = DaemonImplementation(options=options)
        daemon.preserve_standard_streams = True

        daemon.launch()

        self.assertIs(sys.stdin, daemon._daemon_context.stdin)
        self.assertIs(sys.stdout, daemon._daemon_context.stdout)
        self.assertIs(sys.stderr, daemon._daemon_context.stderr)

    def test_launch_preserve_standard_streams_not_set(self):
        """
        When preserve_standard_streams is not set, the new daemon will use
        a dedicated set of standard streams.
        """
        pid_path = self.getPIDPath()
        options = self.Bunch(pid=pid_path)
        daemon = DaemonImplementation(options=options)
        daemon.preserve_standard_streams = False

        daemon.launch()

        self.assertIsNone(daemon._daemon_context.stdin)
        self.assertIsNone(daemon._daemon_context.stdout)
        self.assertIsNone(daemon._daemon_context.stderr)

    def test_launch_detach_process(self):
        """
        At launch, detach_process is copied to the internal DaemonContext
        instance.
        """
        pid_path = self.getPIDPath()
        options = self.Bunch(pid=pid_path)
        daemon = DaemonImplementation(options=options)
        daemon.detach_process = object()

        daemon.launch()

        self.assertEqual(
            daemon.detach_process,
            daemon._daemon_context.detach_process,
            )

    def test_launch_unknown_pid(self):
        """
        An error is raised when the pid option specifies an unreachable path.
        """
        options = self.Bunch(pid='bad/path/pid-file')
        daemon = DaemonImplementation(options=options)

        with self.assertRaises(CompatError) as context:
            daemon.launch()

        self.assertCompatError(1008, context.exception)

    def test_launch_success(self):
        """
        When launching the daemon it will call the `onEVENT` methods.
        """
        pid_path = self.getPIDPath()
        options = self.Bunch(pid=pid_path)
        daemon = DaemonImplementation(options=options)

        daemon.launch()

        daemon.onInitialize.assert_called_once_with()
        daemon.onStart.assert_called_once_with()
        daemon.onStop.assert_called_once_with(0)
