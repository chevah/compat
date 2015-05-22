# Copyright (c) 2011 Adi Roiban.
"""
Unit tests for get_unicode_argv.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from threading import Timer
import os
import subprocess
import sys

from chevah.compat.testing import CompatTestCase, conditionals


@conditionals.onOSFamily('nt')
class TestUnicodeArguments(CompatTestCase):
    """
    Unit tests for get_unicode_argv.
    """

    def runWithArguments(self, arguments, timeout=10):
        """
        Execute test script with arguments.
        """
        test_file = os.path.join(
            os.path.dirname(__file__), 'helper_sys_argv.py')
        command = [sys.executable, test_file]
        command.extend(arguments)
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            )
        timer = Timer(timeout, lambda p: p.kill(), [proc])
        timer.start()
        stdout, stderr = proc.communicate()
        timer.cancel()
        timer.join(timeout=10)
        if timer.isAlive():
            raise AssertionError('Timeout thread is still alive.')
        return stdout, stderr

    def test_not_arguments(self):
        """
        No arguments result empty list.
        """
        out, err = self.runWithArguments([])
        self.assertEqual('', err)
        self.assertEqual('[][]', out)

    def test_unicode_arguments_with_spaces(self):
        """
        Unicode arguments are preserved together with their spaces.
        """
        name = u'mon\u20acy'

        out, err = self.runWithArguments([
            name.encode(sys.getfilesystemencoding()),
            '--with=simple',
            '--with=some spaces',
            '--with="double qoutes"',
            "--with='simple quotes'"
            ])
        self.assertEqual('', err)

        before = (
            '['
            '\'mon\\x80y\', '
            '\'--with=simple\', '
            '\'--with=some spaces\', '
            '\'--with="double qoutes"\', '
            '"--with=\'simple quotes\'"'
            ']')
        after = (
            '['
            'u\'mon\\u20acy\', '
            'u\'--with=simple\', '
            'u\'--with=some spaces\', '
            'u\'--with="double qoutes"\', '
            'u"--with=\'simple quotes\'"'
            ']'
            )
        self.assertEqual(before + after, out)
