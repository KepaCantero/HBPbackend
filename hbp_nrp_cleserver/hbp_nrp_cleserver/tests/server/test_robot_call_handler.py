# ---LICENSE-BEGIN - DO NOT CHANGE OR MOVE THIS HEADER
# This file is part of the Neurorobotics Platform software
# Copyright (C) 2014,2015,2016,2017 Human Brain Project
# https://www.humanbrainproject.eu
#
# The Human Brain Project is a European Commission funded project
# in the frame of the Horizon2020 FET Flagship plan.
# http://ec.europa.eu/programmes/horizon2020/en/h2020-section/fet-flagships
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
# ---LICENSE-END
"""
This module tests the backend implementation of the simulation lifecycle
"""

import unittest
from mock import Mock, patch
from hbp_nrp_cleserver.server._RobotCallHandler import RobotCallHandler

__author__ = 'Hossain Mahmud'

class TestRobotCallHandler(unittest.TestCase):

    def setUp(self):
        self.mocked_robotmanager = patch("hbp_nrp_cleserver.server._RobotCallHandler.RobotManager").start()
        self.mocked_robot = patch("hbp_nrp_cleserver.server._RobotCallHandler.Robot").start()
        self.mocked_clemsg = patch("hbp_nrp_cleserver.server._RobotCallHandler.msg").start()
        self.mocked_parser = patch("hbp_nrp_cleserver.server._RobotCallHandler.robotXmlParser").start()
        self.mocked_os = patch("hbp_nrp_cleserver.server._RobotCallHandler.os").start()
        self.mocked_tf = patch("hbp_nrp_cleserver.server._RobotCallHandler.tf").start()

        self.mocked_assembly = Mock()
        self.handler = RobotCallHandler(self.mocked_assembly)

    def tearDown(self):
        self.mocked_robotmanager.stop()
        self.mocked_robot.stop()
        self.mocked_clemsg.stop()
        self.mocked_parser.stop()
        self.mocked_os.stop()
        self.mocked_tf.stop()

    def test_get_robots(self):
        someDict = {'a': Mock(), 'x': Mock()}
        self.mocked_assembly.robotManager.get_robot_dict.return_value = someDict
        x = self.handler.get_robots()

        self.assertTrue(len(x) is len(someDict))

    def test_add_robot(self):
        self.mocked_assembly.storage_client = Mock()
        self.mocked_assembly.simDir = '/somewhere/over/the/rainbow'
        self.mocked_assembly.token = 'my_awesome_token'
        self.mocked_assembly.ctx_id = 0xFFFF

        with patch("zipfile.ZipFile") as zipfile, \
            patch("hbp_nrp_backend.storage_client_api.StorageClient.find_file_in_paths") as findFile, \
            patch("hbp_nrp_backend.storage_client_api.StorageClient.get_model_basepath") as getpath:

            ret, status = self.handler.add_robot('id', 'over/the/rainbow', True)
            self.mocked_assembly.storage_client.get_custom_model.assert_called_once_with(
                self.mocked_assembly.token,
                self.mocked_assembly.ctx_id,
                '{"uuid": "robots%2Fover%2Fthe%2Frainbow"}'
            )

            ret, status = self.handler.add_robot('id', 'over/the/rainbow')

    def test_delete_robot(self):
        self.mocked_assembly.robotManager.get_robot.return_value.SDFFileAbsPath = "somewhere/over/the/rainbow"
        self.mocked_assembly.robotManager = Mock()

        ret, status = self.handler.delete_robot('id')

        self.mocked_assembly.robotManager.remove_robot.assert_called_once_with('id')