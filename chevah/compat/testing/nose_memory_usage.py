"""
This plugin provides memory usage .
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from six.moves import range
import operator

import nose
from nose.plugins.base import Plugin

# Number of tests to show in final report.
TOP_COUNT = 10


class MemoryUsage(Plugin):
    """
    This plugin reports memory for each test.

    It reports the 10 most memory hungry tests.
    """

    name = 'memory-usage'
    score = 1

    def getPeakMemoryUsage(self):
        """
        Method to prevent circular import.
        """
        from chevah.compat.testing import ChevahTestCase  # pragma: no cover
        return ChevahTestCase.getPeakMemoryUsage()  # pragma: no cover

    def configure(self, options, config):
        """Configures the test timer plugin."""
        super(MemoryUsage, self).configure(options, config)
        self._memory_usage = {}

    def startTest(self, test):
        """
        Called before starting the test.
        """
        self._start_rss = self.getPeakMemoryUsage()

    def stopTest(self, test):
        end_rss = self.getPeakMemoryUsage()
        self._memory_usage[test.id()] = end_rss - self._start_rss

    def report(self, stream):
        """Report the test times"""
        if not self.enabled:
            return

        sorted_usage = sorted(
            iter(self._memory_usage.items()),
            key=operator.itemgetter(1),
            )

        stream.writeln('-' * 70)
        stream.writeln('Memory usage top %s report:\n' % (TOP_COUNT))
        tests_count = len(sorted_usage)
        if not tests_count:
            stream.writeln('No tests were executed.')
            return

        test_start = tests_count - TOP_COUNT
        if test_start < 0:
            test_start = 0

        for index in range(tests_count - 1, test_start - 1, -1):
            test_id, memory_usage = sorted_usage[index]
            stream.writeln("%0.4f: %s" % (memory_usage, test_id))


if __name__ == '__main__':
    nose.main(addplugins=[MemoryUsage()])
