# ---LICENSE-BEGIN - DO NOT CHANGE OR MOVE THIS HEADER
# This file is part of the Neurorobotics Platform software
# Copyright (C) 2014,2015,2016,2017 Human Brain Project
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
This module contains REST services for getting neurons from a running simulation
"""

__author__ = "Bernd Eckstein"

from flask_restful import Resource, fields
from flask_restful_swagger import swagger

from hbp_nrp_backend.rest_server.__SimulationControl import _get_simulation_or_abort

# pylint: disable=no-self-use


@swagger.model
class NeuronParameter(object):
    """
    NeuronParameter
    Only used for swagger documentation
    """

    resource_fields = {
        'parameterName': fields.String,
        'value': fields.Float,
    }
    required = ['parameterName', 'value']


@swagger.model
@swagger.nested(parameters=NeuronParameter.__name__)
class Population(object):
    """
    Population
    Only used for swagger documentation
    """

    resource_fields = {
        'name': fields.String,
        'neuron_model': fields.String,
        'parameters': fields.List(fields.Nested(NeuronParameter.resource_fields)),
        'gids': fields.List(fields.Integer),
    }
    required = ['neuron_model', 'name', 'gids', 'parameters']


@swagger.model
@swagger.nested(neurons=Population.__name__)
class Populations(object):
    """
    Populations
    Only used for swagger documentation
    """

    resource_fields = {
        'populations': fields.List(fields.Nested(Population.resource_fields)),
    }
    required = ['populations']


class SimulationPopulations(Resource):
    """
    This resource handles getting the populations of a brain in a simulation,
    by retreiving the neurons of the respective CLE instance.
    """

    @swagger.operation(
        notes='Gets the neurons of the given simulation.',
        responseClass=Populations.__name__,
        parameters=[
            {
                "name": "sim_id",
                "description": "The ID of the simulation whose neurons shall be retrieved",
                "required": True,
                "paramType": "path",
                "dataType": int.__name__
            }
        ],
        responseMessages=[
            {
                "code": 404,
                "message": "The simulation was not found"
            },
            {
                "code": 200,
                "message": "Success. The neurons of the simulation with the given ID are retrieved"
            }
        ]
    )
    def get(self, sim_id):
        """
        Gets the neurons of the brain in a simulation with the specified simulation id.

        :param sim_id: The simulation id
        :>json dict Populations: The populations as json: \
          {\
             populations: [
                 { \
                    name: "string", \
                    neuron_model: "string", \
                    gids: [0, 8, 15], \
                    parameters: [ \
                        { \
                          parameterName:  "string", \
                          value: 0.0 \
                        }
                    ] \
                 } \
              ] \
          }
        :status 404: The simulation with the given ID was not found
        :status 200: The neurons of the simulation with the given ID where successfully retrieved
        """
        simulation = _get_simulation_or_abort(sim_id)

        # Get Neurons from cle
        neurons = simulation.cle.get_populations()

        return neurons, 200
