# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
'''Unix specific functionality for launching an Unix daemon.'''
from __future__ import with_statement
import daemon
import os
import signal
import sys

from zope.interface import implements

from chevah.utils.helpers import _
from chevah.utils.interfaces import IDaemon
from chevah.utils.logger import log, Logger


class ChevahDaemon(object):
    '''Handles creation and closing of an Unix daemon.'''

    implements(IDaemon)

    def __init__(self, options):
        '''See `IDaemon`.'''
        self.options = options
        self._process = None

    def _onStopSignal(self, signum, frame):
        '''Called when SIGINT or SIGTERM are received.'''
        self.stop()

    def launch(self):
        '''See `IDaemon`.'''
        daemon_context = daemon.DaemonContext()
        daemon_context.detach_process = True
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
            log(1008, _(u'Could not open PID file at %s.' % (pid_path)))
            sys.exit(1)

        self.initialize()

        daemon_context.files_preserve = Logger.getAllOpenFileHandlers()

        with daemon_context:
            try:
                pid_file = open(self.options.pid, 'w')
                pid_file.write('%d' % os.getpid())
                pid_file.close()
            except IOError:
                log(1008, _(u'Could not write PID file at %s.' % (pid_path)))
                sys.exit(1)

            self.start()

            try:
                os.remove(self.options.pid)
            except:
                # We don't care if remove operation fail or succed.
                # We are going to close the server anyway.
                # Just change the exit value to signal that something went
                # wrong.
                # pylint: disable=W0702
                log(1009, _(u'Could not remove PID file at %s.' % (pid_path)))
                self.stop()
                sys.exit(3)
            self.stop()
            sys.exit(0)

    def initialize(self):
        '''Initialize the daemon.'''
        raise NotImplementedError(
            'Use this method for initializing your daemon.')

    def start(self):
        '''Starts the daemon.'''
        raise NotImplementedError(
            'Use this method for starting your daemon.')

    def stop(self):
        '''Stops the daemon.'''
        raise NotImplementedError(
            'Use this method for stoping your daemon.')
