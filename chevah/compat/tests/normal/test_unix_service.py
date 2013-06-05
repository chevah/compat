# Copyright (c) 2012 Adi Roiban.
# See LICENSE for details.
"""
Tests for Unix Daemon.
"""
import os

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
        self.getOpenFiles = mk.makeMock()
        self.getOpenFiles.return_value = [100, 123]
        self.onInitialize = mk.makeMock()
        self.onStart = mk.makeMock()
        self.onStop = mk.makeMock()


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
        # We set the path to self.test_segments to be automatically
        # cleaned.
        (path, self.test_segments) = mk.fs.makePathInTemp()
        return path

    def test_init(self):
        """
        Check initialization.
        """
        options = object()
        daemon = DaemonImplementation(options=options)

        self.assertProvides(IDaemon, daemon)
        self.assertEqual(options, daemon.options)
        self.assertIsFalse(daemon.PRESERVE_STANDARD_STREAMS)
        self.assertIsTrue(daemon.DETACH_PROCESS)

    def test_launch_PRESERVE_STANDARD_STREAMS(self):
        """
        When PRESERVE_STANDARD_STREAMS is set, the new daemon will
        inherit the standard stream.
        """
        pid_path = self.getPIDPath()
        options = self.Bunch(pid=pid_path)
        daemon = DaemonImplementation(options=options)
        daemon.PRESERVE_STANDARD_STREAMS = True

        daemon.launch()

        self.assertIsNotNone(daemon._daemon_context.stdin)
        self.assertIsNotNone(daemon._daemon_context.stdout)
        self.assertIsNotNone(daemon._daemon_context.stderr)

    def test_launch_DETACH_PROCESS(self):
        """
        At launch, DETACH_PROCESS is copied to the internal DeamonContext
        instance.
        """
        pid_path = self.getPIDPath()
        options = self.Bunch(pid=pid_path)
        daemon = DaemonImplementation(options=options)
        daemon.DETACH_PROCESS = object()

        daemon.launch()

        self.assertEqual(
            daemon.DETACH_PROCESS,
            daemon._daemon_context.detach_process,
            )

    def test_launch_unknown_pid(self):
        """
        An error is raised when the pid option specified an unreachable path.
        """
        options = self.Bunch(pid='bad/path/pid-file')
        daemon = DaemonImplementation(options=options)

        with self.assertRaises(CompatError) as context:
            daemon.launch()

        self.assertExceptionID(1008, context.exception)

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
