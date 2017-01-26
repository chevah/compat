'''This plugin provides a list of failed, errors, skiped tests.

Add this command to the way you execute nose::

    --with-run-reporter

'''
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import nose
from nose.plugins.base import Plugin


class RunReporter(Plugin):
    '''This plugin reports the list of skiped tests.'''

    name = 'run-reporter'
    score = 1

    def configure(self, options, config):
        """Configures the test timer plugin."""
        super(RunReporter, self).configure(options, config)
        self.config = config
        self._timed_tests = {'inner': {}, 'outer': {}}
        self._timer = {'inner': 0, 'outer': 0}

    def finalize(self, result):
        """Report the test times"""
        if not self.enabled:  # pragma: no cover
            return

        def format_test_id(test_id):
            return test_id.replace('.Test', ':Test')

        if len(result.skipped):
            result.stream.write('\nSkipped tests:\n')
        for test in result.skipped:
            result.stream.write(format_test_id(test[0].id()) + '\n')

        if len(result.errors):  # pragma: no cover
            result.stream.write('\nError tests:\n')
        for test in result.errors:  # pragma: no cover
            result.stream.write(format_test_id(test[0].id()) + '\n')

        if len(result.failures):  # pragma: no cover
            result.stream.write('\nFailed tests:\n')
        for test in result.failures:  # pragma: no cover
            result.stream.write(format_test_id(test[0].id()) + '\n')

        result.stream.write('\n')


if __name__ == '__main__':
    nose.main(addplugins=[RunReporter()])
