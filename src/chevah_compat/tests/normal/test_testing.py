# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Tests for the testing infrastructure.
"""
from threading import Thread, Event

from chevah_compat.testing import ChevahTestCase, mk


class TestFactory(ChevahTestCase):
    """
    Test for factory methods.
    """

    def test_avatar_unicode(self):
        """
        Check that avatar is created with unicode members.
        """
        avatar = mk.makeFilesystemApplicationAvatar()
        self.assertIsInstance(avatar.name, str)
        self.assertIsInstance(avatar.home_folder_path, str)

    def test_tearDown_excepted_threads(self):
        """
        Will not fail if a thread name is in excepted_threads.
        """
        event = Event()

        class TestThread(Thread):
            def run(self):
                event.wait()

        self.excepted_threads = self.excepted_threads + ['TestThread']

        thread = TestThread(name="TestThread")
        thread.start()

        self.tearDown()

        self.assertTrue(thread.is_alive())
        event.set()

        # Wait for the thread to stop.
        thread.join()
        self.assertFalse(thread.is_alive())

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
        thread.join()

    def test_tearDown_excepted_threads_contains(self):
        """
        Will not fail if part of the thread name is in excepted_threads.
        """
        event = Event()

        class TestThread(Thread):
            def run(self):
                event.wait()

        self.excepted_threads = self.excepted_threads + ['TestTh']

        thread = TestThread(name="TestThread")
        thread.start()

        self.tearDown()

        self.assertTrue(thread.is_alive())
        event.set()

        # Wait for the thread to stop.
        thread.join()
        self.assertFalse(thread.is_alive())
