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
Unit tests for the __SimulationResetStorage module.
"""

__author__ = 'Alessandro Ambrosano, Ugo Albanese, Georg Hinkel'

import unittest
import mock
from mock import mock_open
import json
from mock import patch, ANY
import os
import tempfile
import shutil
from hbp_nrp_backend.cle_interface.ROSCLEClient import ROSCLEClientException
from hbp_nrp_backend.rest_server.tests import RestTest
from hbp_nrp_backend.simulation_control import simulations, Simulation
from cle_ros_msgs.srv import ResetSimulationRequest
from hbp_nrp_commons.generated import bibi_api_gen, exp_conf_api_gen
from pyxb import ValidationError

from hbp_nrp_backend.rest_server.__SimulationResetStorage import SimulationResetStorage


PATH = os.path.split(__file__)[0]
EXPERIMENT_DATA_PATH = os.path.join(PATH, 'experiments', 'experiment_data')


class TestSimulationResetStorage(RestTest):

    def setUp(self):
        self.storage_client = SimulationResetStorage.storage_client
        self.mock_storage_client = mock.MagicMock()

        SimulationResetStorage.storage_client = self.mock_storage_client
        del simulations[:]
        simulations.append(Simulation(
            0, 'experiments/experiment_data/test_1.exc', 'default-owner', 'created'))
        simulations.append(Simulation(
            1, 'experiments/experiment_data/test_1.exc', 'im-not-the-owner', 'created'))

        self.experiment_id = "0000-0000"
        # Correct request
        self.correct_reset_url = '/simulation/0/{exp_id}/reset'.format(exp_id=self.experiment_id)

    def tearDown(self):
        SimulationResetStorage.storage_client = self.storage_client

    @patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage._get_sdf_world_from_storage')
    def test_put_reset(self, mock_get_sdf):
        simulations[0].cle = mock.MagicMock()
        mock_get_sdf.return_value = '<sdf></sdf>'

        response = self.client.put(self.correct_reset_url, data=json.dumps({
            'resetType': ResetSimulationRequest.RESET_ROBOT_POSE
        }))
        self.assertEqual(200, response.status_code)
        simulations[0].cle.reset.assert_called()

    def test_put_reset_too_many_parameters(self):
        # Invalid request, too many parameters
        response = self.client.put(self.correct_reset_url, data=json.dumps({
            'resetType': ResetSimulationRequest.RESET_ROBOT_POSE,
            'randomInvalidParameter': False
        }))
        self.assertEqual(400, response.status_code)

    def test_put_reset_missing_parameters(self):
        # Invalid request, missing parameters
        response = self.client.put(self.correct_reset_url, data=json.dumps({}))
        self.assertEqual(400, response.status_code)

    def test_put_reset_sim_not_exist(self):
        # This simulation doesn't exist
        response = self.client.put(
            '/simulation/2/' + self.experiment_id + '/reset')
        self.assertEqual(404, response.status_code)

    def test_put_reset_not_owner(self):
        # I'm not the owner of this one
        response = self.client.put(
            '/simulation/1/' + self.experiment_id + '/reset')
        self.assertEqual(401, response.status_code)

    def test_put_reset_throws(self):
        # Now the request is fine, but something goes wrong out of the
        # backend's reach
        simulations[0].cle = mock.MagicMock()
        simulations[0].cle.reset.side_effect = ROSCLEClientException()
        response = self.client.put(self.correct_reset_url, data=json.dumps({
            'resetType': ResetSimulationRequest.RESET_ROBOT_POSE
        }))
        self.assertEqual(500, response.status_code)

    def test_put_reset_brain_unsupported(self):
        # Invalid request, missing parameters
        response = self.client.put(self.correct_reset_url, data=json.dumps({
            'resetType': ResetSimulationRequest.RESET_BRAIN
        }))
        self.assertEqual(400, response.status_code)


    @patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage._get_sdf_world_from_storage')
    @patch("hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage._get_brain_info_from_storage")
    @patch("hbp_nrp_backend.storage_client_api.StorageClient.StorageClient")
    @patch("hbp_nrp_backend.simulation_control.__Simulation.Simulation.lifecycle")
    def test_reset_is_called_properly(self, mock_lifecycle, mock_storage_client,
                                      mock_get_brain_info_from_storage,
                                      mock_get_sdf_world_from_storage):
        simulations[0].cle = mock.MagicMock()
        simulations[0].cle.set_simulation_transfer_function.return_value = None

        mock_get_brain_info_from_storage.return_value = os.path.join(PATH, 'models/braitenberg.py'), {}, {}

        mock_get_sdf_world_from_storage.return_value = '<sdf></sdf>'
        experiment_file_path = os.path.join(PATH, 'experiments/experiment_data/test_1.exc')

        response = self.client.put(self.correct_reset_url, data=json.dumps({
            'resetType': ResetSimulationRequest.RESET_ROBOT_POSE
        }))
        self.assertEqual(200, response.status_code)
        simulations[0].cle.reset.assert_called_with(ResetSimulationRequest.RESET_ROBOT_POSE)

        mock_lifecycle.return_value = mock.MagicMock(experiment_path="")
        mock_storage_client.clone_all_experiment_files.return_value = experiment_file_path
        response = self.client.put(self.correct_reset_url, data=json.dumps({
            'resetType': ResetSimulationRequest.RESET_FULL
        }))

        # this test will fail once the reset functionality is working again (see issue report NRRPLT-4860)
        # at that moment, 500 should be replaced by 200 and RESET_ROBOT_POSE
        # should be replaced by RESET_FULL in the next lines
        self.assertEqual(500, response.status_code)
        simulations[0].cle.reset.assert_called_with(ResetSimulationRequest.RESET_ROBOT_POSE)

        fake_world_sdf_string = '<sdf></sdf>'

        with patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage._get_sdf_world_from_storage') \
                as mock_get_sdf:
            mock_get_sdf.return_value = fake_world_sdf_string

            self.client.put(self.correct_reset_url, data=json.dumps({
                'resetType': ResetSimulationRequest.RESET_WORLD
            }))
            simulations[0].cle.reset.assert_called_with(ResetSimulationRequest.RESET_WORLD,
                                                        world_sdf=fake_world_sdf_string)

    @patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.UserAuthentication.get_header_token')
    def test_get_sdf_world_from_storage(self, mock_get_header_token):

        bibi_original_path = os.path.join(os.path.split(
            __file__)[0], "experiments", "experiment_data", "bibi_1.bibi")
        bibi_temp_path = os.path.join(tempfile.mkdtemp(), "bibi_test.xml")
        shutil.copyfile(bibi_original_path, bibi_temp_path)

        exp_temp_path = os.path.join(os.path.split(
            __file__)[0], "experiments", "experiment_data", "test_1.exc")

        def fake_get(*args, **kwargs):
            if args[2] == 'experiment_configuration.exc':
                with open(exp_temp_path) as exp_xml:
                    return exp_xml.read()
            with open(bibi_temp_path) as bibi_xml:
                return bibi_xml.read()
        self.mock_storage_client.get_file = fake_get

        fake_filepath = '/abc/cde'
        self.mock_storage_client.clone_file = fake_filepath
        fake_world_sdf_string = '<sdf></sdf>'
        with patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.open', mock_open(read_data=fake_world_sdf_string), create=True) as m:
            # call target function
            world_sdf_string = SimulationResetStorage._get_sdf_world_from_storage(
                self.experiment_id, None)

        # assertions
        mock_get_header_token.assert_called()
        self.assertEqual(self.mock_storage_client.clone_file, fake_filepath)

        self.assertNotEqual(world_sdf_string, fake_world_sdf_string)

    @patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.UserAuthentication.get_header_token')
    def test_get_sdf_world_from_storage_user_model(self, mock_get_header_token):

        bibi_original_path = os.path.join(os.path.split(
            __file__)[0], "experiments", "experiment_data", "bibi_4.bibi")
        bibi_temp_path = os.path.join(tempfile.mkdtemp(), "bibi_test.xml")
        shutil.copyfile(bibi_original_path, bibi_temp_path)

        exp_temp_path = os.path.join(os.path.split(
            __file__)[0], "experiments", "experiment_data", "test_5.exc")

        def fake_get(*args, **kwargs):
            if args[2] == 'experiment_configuration.exc':
                with open(exp_temp_path) as exp_xml:
                    return exp_xml.read()
            with open(bibi_temp_path) as bibi_xml:
                return bibi_xml.read()
        self.mock_storage_client.get_file = fake_get

        fake_filepath = '/abc/cde'
        self.mock_storage_client.clone_file = fake_filepath
        fake_world_sdf_string = '<sdf></sdf>'
        with patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.open', mock_open(read_data=fake_world_sdf_string), create=True) as m:
            # call target function
            world_sdf_string = SimulationResetStorage._get_sdf_world_from_storage(
                self.experiment_id, None)

        # assertions
        mock_get_header_token.assert_called()
        self.assertEqual(self.mock_storage_client.clone_file, fake_filepath)

        self.assertNotEqual(world_sdf_string, fake_world_sdf_string)

    @patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.get_all_neurons_as_dict')
    @patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.UserAuthentication.get_header_token')
    def test_get_brain_info_from_storage(self, mock_get_brain_info, mock_get_all_neurons_as_dict):

        dummy_dir = "/my/temp/dir"

        self.mock_storage_client.clone_file.return_value = os.path.join(
            dummy_dir, "brain.py")

        bibi_original_path = os.path.join(os.path.split(
            __file__)[0], "experiments", "experiment_data", "bibi_1.bibi")
        bibi_temp_path = os.path.join(tempfile.mkdtemp(), "bibi_test.xml")
        shutil.copyfile(bibi_original_path, bibi_temp_path)

        exp_temp_path = os.path.join(os.path.split(
            __file__)[0], "experiments", "experiment_data", "test_1.exc")

        def fake_get(*args, **kwargs):
            if args[2] == 'experiment_configuration.exc':
                with open(exp_temp_path) as exp_xml:
                    return exp_xml.read()
            with open(bibi_temp_path) as bibi_xml:
                return bibi_xml.read()
        self.mock_storage_client.get_file = fake_get

        dummy_populations = {'pop1': slice(0, 1, 1), 'pop2': slice(1, 2, 1)}
        mock_get_all_neurons_as_dict.return_value = dummy_populations

        data_from_storage, populations, _ = SimulationResetStorage._get_brain_info_from_storage(self.experiment_id, None)

        self.assertEqual(data_from_storage, os.path.join(dummy_dir, 'brain.py'))
        self.assertEqual(
            '[name: pop2\ntype: 1\nids: []\nstart: 1\nstop: 2\nstep: 1, name: pop1\ntype: 1\nids: []\nstart: 0\nstop: 1\nstep: 1]',
            str(populations).replace('\"', ''))
        # Converting the population list to a String using str(populations) generates double quotes
        # around the population name if run locally, but does not generate the double quotes on
        # jenkins for now. So this is just a workaround to remove any generated double quotes around
        # population names.

    @patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.get_all_neurons_as_dict')
    @patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.UserAuthentication.get_header_token')
    def test_get_brain_info_from_storage_user_model(self, mock_get_brain_info, mock_get_all_neurons_as_dict):

        dummy_dir = "/my/temp/dir"

        self.mock_storage_client.clone_file.return_value = os.path.join(
            dummy_dir, "brain.py")

        bibi_original_path = os.path.join(os.path.split(
            __file__)[0], "experiments", "experiment_data", "bibi_4.bibi")
        bibi_temp_path = os.path.join(tempfile.mkdtemp(), "bibi_test.xml")
        shutil.copyfile(bibi_original_path, bibi_temp_path)

        exp_temp_path = os.path.join(os.path.split(
            __file__)[0], "experiments", "experiment_data", "test_5.exc")

        def fake_get(*args, **kwargs):
            if args[2] == 'experiment_configuration.exc':
                with open(exp_temp_path) as exp_xml:
                    return exp_xml.read()
            with open(bibi_temp_path) as bibi_xml:
                return bibi_xml.read()
        self.mock_storage_client.get_file = fake_get

        dummy_populations = {'pop1': slice(0, 1, 1), 'pop2': slice(1, 2, 1)}
        mock_get_all_neurons_as_dict.return_value = dummy_populations
        with patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.open', mock_open(read_data='Fake_data'), create=True) as m:
            data_from_storage, populations, _ = SimulationResetStorage._get_brain_info_from_storage(
                self.experiment_id, None)

        self.assertEqual(
            '[name: pop2\ntype: 1\nids: []\nstart: 1\nstop: 2\nstep: 1, name: pop1\ntype: 1\nids: []\nstart: 0\nstop: 1\nstep: 1]',
            str(populations).replace('\"', ''))
        # Converting the population list to a String using str(populations) generates double quotes
        # around the population name if run locally, but does not generate the double quotes on
        # jenkins for now. So this is just a workaround to remove any generated double quotes around
        # population names.

    @patch("hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage._get_brain_info_from_storage")
    @patch("hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage.reset_from_storage_all")
    @patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage._get_sdf_world_from_storage')
    def test_full_reset_ok(self, mock_get_sdf, mock_reset_from_storage, mock_get_brain_info):
        mock_reset_from_storage.side_effect = None
        mock_get_sdf.return_value = '<sdf></sdf>'
        mock_get_brain_info.return_value = os.path.join(PATH, 'models/braitenberg.py'), None, None
        simulations[0].cle = mock.MagicMock()

        response = self.client.put(self.correct_reset_url, data=json.dumps({
            'resetType': ResetSimulationRequest.RESET_ROBOT_POSE,
            'contextId': None
        }))
        self.assertEqual(200, response.status_code)
        simulations[0].cle.reset.side_effect = None
        response = self.client.put(self.correct_reset_url, data=json.dumps({
            'resetType': ResetSimulationRequest.RESET_FULL,
            'contextId': None
        }))
        simulations[0].cle.reset.assert_called()
        self.assertEqual(response.status_code, 200)

    @patch("os.path.dirname")
    @patch("hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage.reset_brain")
    @patch("hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage.reset_transfer_functions")
    @patch("hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage.reset_state_machines")
    @patch('hbp_nrp_backend.rest_server.__SimulationResetStorage.UserAuthentication.get_header_token')
    def test_reset_from_storage_all(self,
                                    mock_get_header_token,
                                    mock_reset_brain,
                                    mock_resetTFs,
                                    mock_resetSMs,
                                    mock_dirname):
        self.mock_storage_client.clone_all_experiment_files.return_value = \
            {'experiment_conf': 'fakeFolder/fakeExp'}

        mock_reset_brain.return_value = None
        mock_resetTFs.return_value = None
        mock_resetSMs.return_value = None
        mock_dirname.return_value = os.path.join(PATH, 'experiments/experiment_data')
        simulations[0].cle = mock.MagicMock()
        simulations[0].cle.set_simulation_transfer_function.return_value = None
        simulations[0].lifecycle.experiment_path = os.path.join(PATH, 'experiments/experiment_data/test_5.exc')

        SimulationResetStorage.reset_from_storage_all(simulations[0], 'ExperimentId', 'fakeContextID')

    @patch("hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage._get_brain_info_from_storage")
    def test_reset_brain(self, mock_get_brain_info):
        simulations[0].cle = mock.MagicMock()

        simulations[0].cle.set_simulation_brain.return_value = mock.Mock(error_message="",
                                                                         error_line=10,
                                                                         error_column=50)
        simulations[0].cle.set_simulation_populations.return_value = mock.Mock(message='')
        mock_get_brain_info.return_value = os.path.join(PATH,
                                                        'models/braitenberg.py'), None, {u'record': slice(0L, 2L, 1L), u'neurons': slice(0L, 2L, 1L)}

        SimulationResetStorage.reset_brain(simulations[0], 'expId', 'contextId')
        SimulationResetStorage._get_brain_info_from_storage.assert_called_with('expId', 'contextId')

    @patch("hbp_nrp_backend.rest_server.__SimulationResetStorage.SimulationResetStorage._get_brain_info_from_storage")
    def test_reset_brain_throw(self, mock_get_brain_info):
        simulations[0].cle = mock.MagicMock()
        simulations[0].cle.set_simulation_brain.return_value = mock.Mock(error_message="error",
                                                                         error_line=10,
                                                                         error_column=50)

        mock_get_brain_info.return_value = (os.path.join(PATH, 'models/braitenberg.py'),
                                            None,
                                            {u'record': slice(0L, 2L, 1L), u'neurons': slice(0L, 2L, 1L)})

        with self.assertRaises(ROSCLEClientException) as context:
            SimulationResetStorage.reset_brain(simulations[0], 'expId', 'contextId')

        self.assertEqual(
            'error, column: 50', context.exception.message)

    def test_reset_transfer_functions(self):
        simulations[0].cle = mock.MagicMock()
        tf_sources_list = ['# Imported Python Transfer Function\n@nrp.MapCSVRecorder("recorder", filename="all_spikes.csv", headers=["id", "time"])\n@nrp.MapSpikeSink("record_neurons", nrp.brain.record, nrp.spike_recorder)\n@nrp.Neuron2Robot(Topic(\'/monitor/spike_recorder\', cle_ros_msgs.msg.SpikeEvent))\ndef csv_spike_monitor(t, recorder, record_neurons):\n    for i in range(0, len(record_neurons.times)):\n        recorder.record_entry(\n            record_neurons.times[i][0],\n            record_neurons.times[i][1]\n        )\n', '# Imported Python Transfer Function\n#\nimport hbp_nrp_cle.tf_framework as nrp\n# This specifies that the neurons 0 to 2 of the circuit population\n# should be monitored. You can see them in the spike train widget\n@nrp.NeuronMonitor(nrp.brain.record, nrp.spike_recorder)\ndef all_neurons_spike_monitor(t):\n    # Uncomment to log into the \'log-console\' visible in the simulation\n    # clientLogger.info("Time: ", t)\n    return True\n#\n',
                          '# Imported Python Transfer Function\n#\nimport hbp_nrp_cle.tf_framework as nrp\nfrom hbp_nrp_cle.robotsim.RobotInterface import Topic\nimport std_msgs.msg\n@nrp.MapSpikeSink("output_neuron", nrp.brain.neurons[1], nrp.leaky_integrator_alpha)\n@nrp.Neuron2Robot(Topic(\'/robot/eye_version/pos\', std_msgs.msg.Float64))\n# Example TF: get output neuron voltage and output some value on robot actuator to change eyes position whever an output spike is detected. You could do something else with the voltage here and command the robot accordingly.\ndef turn_eyes(t, output_neuron):\n    data = 0.3\n    if output_neuron.voltage < 0.0001:\n        data = -0.3\n    return std_msgs.msg.Float64(data)\n#\n', '# Imported Python Transfer Function\n#\nfrom sensor_msgs.msg import JointState\n@nrp.MapRobotSubscriber("joints", Topic("/robot/joints", JointState))\n@nrp.Neuron2Robot(Topic(\'/joint_states\', JointState))\ndef joint_states_passthrough(t, joints):\n    return joints.value\n#\n', '# Imported Python Transfer Function\n#\nimport hbp_nrp_cle.tf_framework as nrp\nfrom hbp_nrp_cle.robotsim.RobotInterface import Topic\nimport sensor_msgs.msg\n@nrp.MapRobotSubscriber("camera", Topic(\'/icub_model/left_eye_camera/image_raw\', sensor_msgs.msg.Image))\n@nrp.MapSpikeSource("input_neuron", nrp.brain.neurons[0], nrp.poisson)\n@nrp.Robot2Neuron()\n# Example TF: get image and fire at constant rate. You could do something with the image here and fire accordingly.\ndef grab_image(t, camera, input_neuron):\n    image = camera.value\n    input_neuron.rate = 10\n#\n']
        tf_activation_list = [True, True]
        simulations[0].cle.get_simulation_transfer_functions.return_value = (tf_sources_list, tf_activation_list)
        simulations[0].cle.add_simulation_transfer_function.return_value = None
        bibi_file_abs = os.path.join(os.path.split(
            __file__)[0], "experiments", "experiment_data", "bibi_1.bibi")
        with open(bibi_file_abs) as b_file:
            bibi = bibi_api_gen.CreateFromDocument(b_file.read())
        SimulationResetStorage.reset_transfer_functions(simulations[0], bibi, EXPERIMENT_DATA_PATH)
        simulations[0].cle.get_simulation_transfer_functions.assert_called()
        simulations[0].cle.delete_simulation_transfer_function.assert_called_with('grab_image')


if __name__ == '__main__':
    unittest.main()
