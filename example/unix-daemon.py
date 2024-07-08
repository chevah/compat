"""
A simple implementation of the Unix daemon.

Is shows how to pass opened files to the forked process.
"""

from __future__ import absolute_import, print_function, unicode_literals

import os
import time

from chevah.compat.unix_service import Daemon

LOG_PATH = '/tmp/py-daemon-example.log'


class Options(object):
    pid = '/tmp/py-daemon-example.pid'


class DaemonImplementation(Daemon):
    """
    A testing implementation of IDaemon.
    """

    _log_fd = None

    def onInitialize(self):
        """
        See: `IDaemon`.
        """
        print('Starting the daemon...still not forked.')
        self._log_fd = os.open(LOG_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)

    def getOpenFiles(self):
        """
        See: `IDaemon`.
        """
        return [self._log_fd]

    def onStart(self):
        """
        See: `IDaemon`.
        """
        os.write(self._log_fd, 'Starting in fork...\n')
        while True:
            time.sleep(1)
            os.write(self._log_fd, '%s Still alive.\n' % (time.time()))

    def onStop(self, exit_code):
        """
        See: `IDaemon`.
        """
        os.write(self._log_fd, 'Stopping in fork %s.\n' % (exit_code,))
        os.close(self._log_fd)
        print('This should not be visible in the console.')


sut = DaemonImplementation(Options())
sut.launch()
