# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Unix specific functionality for launching an Unix daemon.'''
from __future__ import with_statement
import daemon
import os
import signal
import sys

from zope.interface import implements

from chevah.compat.exceptions import CompatError
from chevah.compat.helpers import _
from chevah.compat.interfaces import IDaemon


class Daemon(object):
    """
    Handles running the process a Unix daemon.
    """

    implements(IDaemon)

    PRESERVE_STANDARD_STREAMS = False
    DETACH_PROCESS = True

    def __init__(self, options):
        """
        See `IDaemon`.
        """
        self.options = options
        self._process = None

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
        if self.PRESERVE_STANDARD_STREAMS:
            stdin = sys.stdin
            stdout = sys.stdout
            stderr = sys.stderr

        daemon_context = daemon.DaemonContext(
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            )
        daemon_context.detach_process = self.DETACH_PROCESS
        daemon_context.signal_map = {
            signal.SIGINT: self._onStopSignal,
            signal.SIGTERM: self._onStopSignal,
            }
        daemon_context.working_directory = os.getcwd()

        pid_path = os.path.abspath(self.options.pid)
        try:
            pid_file = open(pid_path, 'w')
            pid_file.close()
        except IOError:
            raise CompatError(1008,
                _(u'Could not open PID file at %s.' % (pid_path)))

        self.initialize()

        daemon_context.files_preserve = self.getOpenFiles()

        with daemon_context:
            try:
                pid_file = open(self.options.pid, 'w')
                pid_file.write('%d' % os.getpid())
                pid_file.close()
            except IOError:
                raise CompatError(1008,
                    _(u'Could not write PID file at %s.' % (pid_path)))

            self.onStart()

            try:
                os.remove(self.options.pid)
            except:
                # We don't care if remove operation fail or success.
                # We are going to close the server anyway.
                # Just change the exit value to signal that something went
                # wrong.
                self.onStop(1)
                CompatError(1009,
                    _(u'Could not remove PID file at %s.' % (pid_path)))
            self.onStop(0)

    def initialize(self):
        '''Initialize the daemon.'''
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
