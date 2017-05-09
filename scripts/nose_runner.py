# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Helper for executing nose as a separate process.

This is needed since on Unix the tests are executed using sudo.

It is also used to trigger coverage reporting.
"""
import os
import sys

have_coverage = os.environ.get('CODECOV_TOKEN', False)
if have_coverage:
    import coverage
    cov = coverage.Coverage(auto_data=True, config_file='.coveragerc')
    cov.start()
    print 'Coverage reporting started.'
else:
    cov = None

from nose.core import main as nose_main


def main():
    """
    Execute the nose test runner.

    Drop privileges and alter the system argument to remove the
    userid and group id arguments that are only required for the test.
    """
    if len(sys.argv) < 2:
        print (
            u'Run the test suite using drop privileges username as first '
            u'arguments. Use "-" if you do not want elevated mode.')
        sys.exit(1)

    # Delay import after coverage is started.
    from chevah.compat.testing.nose_memory_usage import MemoryUsage
    from chevah.compat.testing.nose_test_timer import TestTimer
    from chevah.compat.testing.nose_run_reporter import RunReporter

    from chevah.compat.testing import ChevahTestCase


    drop_user = sys.argv[1].encode('utf-8')
    ChevahTestCase.initialize(drop_user=drop_user)
    ChevahTestCase.dropPrivileges()

    new_argv = ['chevah-test-runner']
    new_argv.extend(sys.argv[2:])
    sys.argv = new_argv
    plugins = [
        TestTimer(),
        RunReporter(),
        MemoryUsage(),
        ]
    try:
        nose_main(addplugins=plugins)
    except SystemExit, error:
        if cov:
            cov.stop()
            cov.save()
        import threading
        print "Max RSS: %s" % ChevahTestCase.getPeakMemoryUsage()
        threads = threading.enumerate()
        if len(threads) < 2:
            # No running threads, other than main so we can exit as normal.
            sys.exit(error.code)
        else:
            print "There are still active threads: %s" % threads

            # We do a brute force exit here, since sys.exit will wait for
            # unjoined threads.
            # We have to do some manual work to compensate for skipping sys.exit()
            sys.exitfunc()
            # Don't forget to flush the toilet.
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(error.code)

if __name__ == '__main__':
    main()
