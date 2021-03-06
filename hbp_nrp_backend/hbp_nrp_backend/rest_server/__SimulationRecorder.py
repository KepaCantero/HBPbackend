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
'''
This module contains the REST implementation for interaction with the recording functionality
of a simulation.
'''

from flask_restful_swagger import swagger
from flask_restful import Resource

from hbp_nrp_backend.rest_server.__SimulationControl import _get_simulation_or_abort
from hbp_nrp_backend.__UserAuthentication import UserAuthentication
from hbp_nrp_backend import NRPServicesClientErrorException, \
    NRPServicesGeneralException, NRPServicesWrongUserException
from hbp_nrp_backend.rest_server import ErrorMessages
from hbp_nrp_backend.cle_interface.ROSCLEClient import ROSCLEClientException

from cle_ros_msgs.srv import SimulationRecorderRequest

from hbp_nrp_commons.bibi_functions import docstring_parameter

import string

# pylint: disable=no-self-use


class SimulationRecorder(Resource):

    """
    The resource manging interaction with the simulation recorder.
    """

    @swagger.operation(
        notes='Queries the simulation recorder for a value/status.',
        responseClass=string.__name__,
        parameters=[
            {
                'name': 'sim_id',
                'required': True,
                'description': 'The ID of the simulation whose recorder will be queried',
                'paramType': 'path',
                'dataType': int.__name__
            },
            {
                'name': 'command',
                'required': True,
                'description': 'The recorder command to query, supported: [is-recording]',
                'paramType': 'path',
                'dataType': string.__name__
            }
        ],
        responseMessages=[
            {
                'code': 500,
                'message': ErrorMessages.SERVER_ERROR_500
            },
            {
                'code': 404,
                'message': ErrorMessages.SIMULATION_NOT_FOUND_404
            },
            {
                "code": 401,
                "message": ErrorMessages.SIMULATION_PERMISSION_401_VIEW
            },
            {
                'code': 200,
                'message': 'Recorder status retrieved successfully'
            }
        ]
    )
    @docstring_parameter(ErrorMessages.SERVER_ERROR_500,
                         ErrorMessages.SIMULATION_NOT_FOUND_404,
                         ErrorMessages.SIMULATION_PERMISSION_401_VIEW)
    def get(self, sim_id, command):
        """
        Queries the simulation recorder for a value/status. See parameter description for
        supported query commands.

        :param sim_id: The simulation ID to command.
        :param command: The command to query, supported: [is-recording]

        :status 500: {0}
        :status 404: {1}
        :status 401: {2}
        :status 200: Success. The query was issued and value returned.
        """

        # validate simulation id, allow any users/viewers to query recorder
        sim = _get_simulation_or_abort(sim_id)

        if not UserAuthentication.can_view(sim):
            raise NRPServicesWrongUserException()

        # validate the command type
        if command not in ['is-recording', 'is-playingback']:
            raise NRPServicesClientErrorException('Invalid recorder query: %s' % command,
                                                  error_code=404)

        try:
            if command == 'is-recording':
                state = str(sim.cle.command_simulation_recorder(
                    SimulationRecorderRequest.STATE).value)
            elif command == 'is-playingback':
                state = 'False' if sim.playback_path is None else 'True'

            return {'state': state}, 200

        # internal CLE ROS error if service call fails, notify frontend
        except ROSCLEClientException as e:
            raise NRPServicesGeneralException(str(e), 'CLE error', 500)

    @swagger.operation(
        notes='Issues a command to the simulation recorder.',
        responseClass=string.__name__,
        parameters=[
            {
                'name': 'sim_id',
                'required': True,
                'description': 'The ID of the simulation whose recorder will be commanded',
                'paramType': 'path',
                'dataType': int.__name__
            },
            {
                'name': 'command',
                'required': True,
                'description': 'The recorder command, supported: [start, stop, cancel, reset'
                               ', save]',
                'paramType': 'path',
                'dataType': string.__name__
            }
        ],
        responseMessages=[
            {
                'code': 500,
                'message': ErrorMessages.SERVER_ERROR_500
            },
            {
                'code': 404,
                'message': ErrorMessages.SIMULATION_NOT_FOUND_404
            },
            {
                "code": 401,
                "message": ErrorMessages.SIMULATION_PERMISSION_401
            },
            {
                'code': 400,
                'message': 'Invalid/refused command based on recorder state'
            },
            {
                'code': 200,
                'message': 'Recorder command issued successfully'
            }
        ]
    )
    @docstring_parameter(ErrorMessages.SERVER_ERROR_500,
                         ErrorMessages.SIMULATION_NOT_FOUND_404,
                         ErrorMessages.SIMULATION_PERMISSION_401)
    def post(self, sim_id, command):
        """
        Issue user commands to the simulator recorder. See parameter description for
        supported query commands.

        :param sim_id: The simulation ID to command.
        :param command: The command to issue, supported: [start, stop, cancel, reset, save]

        :status 500: {0}
        :status 404: {1}
        :status 401: {2}
        :status 400: The command is invalid/refused by recorder - see message returned.
        :status 200: Success. The command was issued.
        """

        # validate simulation id
        sim = _get_simulation_or_abort(sim_id)

        # only the simulation owner can command the recorder
        if not UserAuthentication.can_modify(sim):
            raise NRPServicesWrongUserException()

        # pure local command to save file to storage
        if command == 'save':
            try:
                file_name = sim.lifecycle.save_record_to_user_storage()
                return {'filename': file_name}, 200

            except Exception as e:
                raise NRPServicesClientErrorException('Cannot copy record to client storage',
                                                      error_code=404)

        else:

            # validate the remote command type
            valid_commands = {'start': SimulationRecorderRequest.START,
                              'stop': SimulationRecorderRequest.STOP,
                              'cancel': SimulationRecorderRequest.CANCEL,
                              'reset': SimulationRecorderRequest.RESET}
            if command not in valid_commands:
                raise NRPServicesClientErrorException('Invalid recorder command: %s' % command,
                                                      error_code=404)

            # command the recorder, if unsuccessful return the error message
            try:
                resp = sim.cle.command_simulation_recorder(valid_commands[command])

                # check the command success, on failure return status 400 + error
                if not resp.value:
                    raise NRPServicesClientErrorException(resp.message)

                # successful, return status 200
                return 'success', 200

            # internal CLE ROS error if service call fails, notify frontend
            except ROSCLEClientException as e:
                raise NRPServicesGeneralException(str(e), 'CLE error', 500)
