"""
This class tests the main startup script.
"""
__author__ = 'Stefan Deser'

from argparse import Namespace
from hbp_nrp_backend import runserver
import logging
from mock import patch, MagicMock
import os
from testfixtures import log_capture
import unittest


class TestScript(unittest.TestCase):

    def setUp(self):
        # a simple mock for the application server
        class MockApp: pass
        self._app = MockApp()
        self._app.run = MagicMock()

        self._args = Namespace()
        self._args.logfile = None
        self._args.port = None

    def tearDown(self):
        # remove all handlers after each test!
        logging.getLogger(runserver.__name__).handlers = []

    @log_capture(level=logging.WARNING)
    def test_run_server_no_arguments(self, logcapture):
        runserver.run_server(self._app, self._args)
        logcapture.check(
                         (runserver.__name__, 'WARNING', 'Could not write to specified logfile or no logfile specified, logging to stdout now!'),
                         (runserver.__name__, 'WARNING', 'Could not parse port, will use default port: ' + str(runserver.DEFAULT_PORT))
                         )
        self.assertTrue(self._app.run.called)
        self._app.run.assert_called_with(port=runserver.DEFAULT_PORT, host=runserver.DEFAULT_HOST)

    def test_run_server_create_logfile(self):
        # create a logfile in the current working directory
        self._args.logfile = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'logfile.log')
        runserver.run_server(self._app, self._args)

        # check if the file exists
        self.assertTrue(os.path.isfile(self._args.logfile))
        os.remove(self._args.logfile)

if __name__ == '__main__':
    unittest.main()