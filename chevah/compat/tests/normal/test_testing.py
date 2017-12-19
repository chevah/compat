# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for the testing infrastructure.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from six import text_type
from threading import Thread, Event

from chevah.compat.testing import ChevahTestCase, mk

import time


class TestFactory(ChevahTestCase):
    """
    Test for factory methods.
    """

    def test_avatar_unicode(self):
        """
        Check that avatar is created with unicode members.
        """
        avatar = mk.makeFilesystemApplicationAvatar()
        self.assertIsInstance(avatar.name, text_type)
        self.assertIsInstance(avatar.home_folder_path, text_type)

    def test_tearDown_excepted_threads(self):
        """
        Will not fail if a thread name is in excepted_threads.
        """
        event = Event()

        class TestThread(Thread):
            def run(self):
                event.wait()

        old_excepted_threads = self.excepted_threads[:]
        self.excepted_threads = self.excepted_threads + ['TestThread']

        thread = TestThread(name="TestThread")
        thread.start()

        self.tearDown()

        self.assertTrue(thread.is_alive())
        event.set()

        # Wait for the thread to stop.
        time.sleep(0.1)
        self.assertFalse(thread.is_alive())

        self.excepted_threads = old_excepted_threads[:]

    def test_tearDown_not_excepted_threads(self):
        """
        Will raise AssertioError fail if a thread name is not in
        excepted_threads.
        """
        event = Event()

        class TestThread(Thread):
            def run(self):
                event.wait()

        thread = TestThread(name="TestThread")
        thread.start()

        with self.assertRaises(AssertionError) as context:
            self.tearDown()

        self.assertContains('TestThread', context.exception.message)

        # Stop the thread.
        event.set()
        time.sleep(0.1)
