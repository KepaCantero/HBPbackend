"""
This module contains the unit tests for the cle launcher initialization
"""

import unittest
import os
from mock import patch, MagicMock, Mock
from hbp_nrp_cleserver.server import CLELauncher
from hbp_nrp_commons.generated import bibi_api_gen, exp_conf_api_gen
from hbp_nrp_cleserver.server.LuganoVizClusterGazebo import XvfbXvnError
from hbp_nrp_cle.mocks.robotsim import MockRobotControlAdapter, MockRobotCommunicationAdapter
from threading import Thread, Event

class MockedGazeboHelper(object):

    def load_gazebo_world_file(self, world):
        return {}, {}

    def __getattr__(self, x):
        return Mock()


MockOs = Mock()
MockOs.environ = {'NRP_MODELS_DIRECTORY': '/somewhere/near/the/rainbow',
                  'ROS_MASTER_URI': "localhost:0815"}
MockOs.path.join.return_value = "/a/really/nice/place"

class SomeWeiredTFException(Exception):
    pass

@patch("hbp_nrp_cleserver.server.CLELauncher.RosControlAdapter", new=MockRobotControlAdapter)
@patch("hbp_nrp_cleserver.server.CLELauncher.RosCommunicationAdapter", new=MockRobotCommunicationAdapter)
@patch("hbp_nrp_cleserver.server.CLELauncher.LocalGazeboBridgeInstance", new=Mock())
@patch("hbp_nrp_cleserver.server.CLELauncher.GazeboHelper", new=MockedGazeboHelper)
@patch("hbp_nrp_cle.cle.ClosedLoopEngine.GazeboHelper", new=MockedGazeboHelper)
@patch("hbp_nrp_cleserver.server.CLELauncher.ClosedLoopEngine", new=Mock())
@patch("hbp_nrp_cleserver.server.CLELauncher.instantiate_communication_adapter", new=Mock())
@patch("hbp_nrp_cleserver.server.CLELauncher.instantiate_control_adapter", new=Mock())
@patch("hbp_nrp_cleserver.server.CLELauncher.os", new=MockOs)
class TestCLELauncherInit(unittest.TestCase):
    def setUp(self):
        dir = os.path.split(__file__)[0]
        with open(os.path.join(dir, "BIBI/milestone2.xml")) as bibi_file:
            bibi = bibi_api_gen.CreateFromDocument(bibi_file.read())
        with open(os.path.join(dir, "ExDConf/ExDXMLExample.xml")) as exd_file:
            exd = exp_conf_api_gen.CreateFromDocument(exd_file.read())
        self.launcher = CLELauncher.CLELauncher(exd, bibi, "/somewhere/over/the/rainbow", "local", None, 42)

    def test_gazebo_location_not_supported_throws_exception(self):
        self.launcher._CLELauncher__gzserver_host = 'not_supported'
        with self.assertRaises(Exception):
            self.launcher.cle_function_init("world_file")

    @patch("hbp_nrp_cleserver.server.CLELauncher.ROSCLEServer")
    @patch("hbp_nrp_cleserver.server.CLELauncher.LocalGazeboServerInstance")
    def test_gazebo_start_exception_catches_xvfbxvn_error(self, mock_gazebo, mock_server):
        mock_gazebo().start.side_effect = XvfbXvnError
        exception_caught = False
        try:
            self.launcher.cle_function_init("world_file")
        except Exception, e:
            self.assertTrue(str(e).startswith("Recoverable error occurred"), msg=e)
            exception_caught = True
        self.assertTrue(exception_caught)

    @patch("hbp_nrp_cleserver.server.CLELauncher.nrp")
    @patch("hbp_nrp_cleserver.server.CLELauncher.ROSCLEServer")
    @patch("hbp_nrp_cleserver.server.CLELauncher.LocalGazeboServerInstance")
    def test_wrong_transfer_function_aborts_initialization(self, mock_gazebo, mock_server, mock_nrp):
        mock_nrp.set_transfer_function.side_effect = SomeWeiredTFException
        with self.assertRaises(SomeWeiredTFException):
            self.launcher.cle_function_init("world_file")

    def __launch_callback(self, _):
        self.launcher.gzserver.gazebo_died_callback()

    @patch("hbp_nrp_cleserver.server.CLELauncher.nrp")
    @patch("hbp_nrp_cleserver.server.CLELauncher.ROSCLEServer")
    @patch("hbp_nrp_cleserver.server.CLELauncher.LocalGazeboServerInstance")
    def test_gazebo_crash_aborts_initialization(self, mock_gazebo, mock_server, mock_nrp):
        mock_gazebo().start.side_effect = self.__launch_callback
        exception_caught = False
        try:
            self.launcher.cle_function_init("world_file")
        except Exception, e:
            self.assertTrue(str(e).startswith("The simulation must abort"), msg=e)
            exception_caught = True
        self.assertTrue(exception_caught)
        mock_server().lifecycle.failed.assert_called_once_with()
        mock_server().lifecycle.stopped.assert_called_once_with()