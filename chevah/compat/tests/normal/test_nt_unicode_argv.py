# Copyright (c) 2011 Adi Roiban.
"""
Unit tests for get_unicode_argv.
"""
from threading import Timer
import os
import subprocess
import sys

from chevah.compat.testing import CompatTestCase, conditionals, mk

if os.name == 'nt':
    import win32service
    from chevah.compat.nt_service import ChevahNTService
    # Silence the linter.
    ChevahNTService
else:
    # This is here to allow defining test classes.
    ChevahNTService = object


#@conditionals.onOSFamily('nt')
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
        self.assertEqual('[]', out)

    def test_unicode_arguments_with_spaces(self):
        """
        Unicode arguments are preserved together with their spaces.
        """
        name = u'mon\u20acy'

        out, err = self.runWithArguments([
            name.encode('utf-8'),
            '--with=simple',
            '--with=some spaces',
            '--with="double qoutes"',
            "--with='simple quotes'"
            ])
        self.assertEqual('', err)
        self.assertEqual(
            '['
            '\'mon\\xe2\\x82\\xacy\', '
            '\'--with=simple\', '
            '\'--with=some spaces\', '
            '\'--with="double qoutes"\', '
            '"--with=\'simple quotes\'"'
            ']',
            out)
