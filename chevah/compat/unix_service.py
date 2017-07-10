# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Unix specific functionality for launching an Unix daemon.'''
from __future__ import with_statement
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import daemon
import os
import signal
import sys

from zope.interface import implements

from chevah.compat import local_filesystem
from chevah.compat.exceptions import CompatError
from chevah.compat.helpers import _
from chevah.compat.interfaces import IDaemon


class Daemon(object):
    """
    Handles running the process a Unix daemon.
    """

    implements(IDaemon)

    DaemonContext = daemon.DaemonContext

    def __init__(self, options):
        """
        See `IDaemon`.
        """
        self.options = options
        self._daemon_context = None
        self.preserve_standard_streams = False
        self.detach_process = True

    def _onStopSignal(self, signum, frame):
        """
        Called when SIGINT or SIGTERM are received.
        """
        self.onStop(0)

    def launch(self):
        """
        See `IDaemon`.
        """
        stdin = None
        stdout = None
        stderr = None
        if self.preserve_standard_streams:
            stdin = sys.stdin
            stdout = sys.stdout
            stderr = sys.stderr

        self._daemon_context = self.DaemonContext(
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            )
        self._daemon_context.detach_process = self.detach_process
        self._daemon_context.signal_map = {
            signal.SIGINT: self._onStopSignal,
            signal.SIGTERM: self._onStopSignal,
            }
        self._daemon_context.working_directory = os.getcwd()

        self.onInitialize()

        self._daemon_context.files_preserve = self.getOpenFiles()

        with self._daemon_context:
            self._writePID()
            self.onStart()
            self._deletePID()
            self.onStop(0)

    def _writePID(self):
        """
        Write process ID in pid file.
        """
        pid_path = os.path.abspath(self.options.pid)
        pid_segments = local_filesystem.getSegmentsFromRealPath(pid_path)
        try:
            pid_file = local_filesystem.openFileForWriting(pid_segments)
            pid_file.write('%d' % os.getpid())
            pid_file.close()
        except (OSError, IOError):
            raise CompatError(
                1008,
                _(u'Could not write PID file at %s.' % (pid_path)),
                )

    def _deletePID(self):
        pid_path = os.path.abspath(self.options.pid)
        pid_segments = local_filesystem.getSegmentsFromRealPath(pid_path)
        try:
            local_filesystem.deleteFile(pid_segments)
        except Exception:
            # We don't care if remove operation fail or success.
            # We are going to close the server anyway.
            # Just change the exit value to signal that something went
            # wrong.
            self.onStop(1)

    def onInitialize(self):
        """
        See: `IDaemon`.
        """
        raise NotImplementedError(
            'Use this method for initializing your daemon.')

    def getOpenFiles(self):
        """
        See: `IDaemon`.
        """
        raise NotImplementedError(
            'Use this method for get the list of file for your daemon.')

    def onStart(self):
        """
        See: `IDaemon`.
        """
        raise NotImplementedError(
            'Use this method for starting your daemon.')

    def onStop(self, exit_code):
        """
        See: `IDaemon`.
        """
        raise NotImplementedError(
            'Use this method for stopping your daemon.')
