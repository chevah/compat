"""
Helpers for running tests for which Twisted reactor in execcuted in a
separate thread.

This code is under based on nose/twistedtools.py which is under LGPL license.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from threading import Thread
import time

_twisted_thread = None
_reactor = None


def get_reactor():
    """
    Start the Twisted reactor in a separate thread, if not already done.
    Returns the reactor.
    The thread will automatically be destroyed when all the tests are done.
    """
    global _twisted_thread, _reactor

    if _twisted_thread:
        return _reactor

    def reactor_run():
        _reactor.__init__()
        _reactor._startedBefore = False
        _reactor._started = False
        _reactor.run(installSignalHandlers=False)

    from twisted.internet import reactor as twisted_reactor
    _reactor = twisted_reactor

    _twisted_thread = Thread(target=reactor_run)
    _twisted_thread.setName('threaded_reactor')
    _twisted_thread.setDaemon(True)
    _twisted_thread.start()

    # Wait a bit for the reactor to start.
    time.sleep(0.01)
    return _reactor


def stop_reactor():
    """
    Stop the reactor and join the reactor thread until it stops.
    Call this function in teardown at the module or package level to
    reset the twisted system after your tests. You *must* do this if
    you mix tests using these tools and tests using twisted.trial.
    """
    global _twisted_thread, _reactor

    if not _twisted_thread:
        return

    def stop_reactor():
        '''Helper for calling stop from withing the thread.'''
        _reactor.stop()

    _reactor.callFromThread(stop_reactor)
    _twisted_thread.join(2)
    if _twisted_thread.isAlive():
        _twisted_thread = None
        raise AssertionError('Failed to stop the reactor.')

    _twisted_thread = None
