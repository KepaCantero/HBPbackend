"""
This module contains the REST services to setup the simulation
"""

__author__ = 'GeorgHinkel'

from hbp_nrp_backend.simulation_control import simulations, Simulation
from hbp_nrp_backend.rest_server import api
from hbp_nrp_backend.rest_server.__SimulationControl import SimulationControl
from flask import request
from flask_restful import Resource, fields, marshal_with
from flask_restful_swagger import swagger

# pylint: disable=R0201


class SimulationSetup(Resource):
    """
    The module to setup simulations
    """

    @swagger.model
    class __NewSimulation(object):
        "Object needed to setup a new simulation"
        resource_fields = {
            'experimentID': fields.String,
        }

    @swagger.operation(
        notes='This is the entry point for the NRP REST server since'
              ' this is where you actually create simulations',
        responseMessages=[
            {
                "code": 400,
                "message": "Experiment ID is not valid"
            },
            {
                "code": 201,
                "message": "Simulation created successfully"
            }
        ],
        parameters=[
            {
                "name": "body",
                "paramType": "body",
                "dataType": __NewSimulation.__name__,
                "required": True
            }
        ]
    )
    def post(self):
        """
        Creates a new simulation. The simulation is not started
        """
        body = request.get_json(force=True)
        sim_id = len(simulations)
        if 'experimentID' in body:
            simulations.append(Simulation(sim_id, body['experimentID']))
        else:
            return "Experiment ID is not valid", 400
        return "Simulation created successfully", 201, \
               {'location': api.url_for(SimulationControl, sim_id=sim_id)}

    @swagger.operation(
        notes='Gets the list of all simulations on the server,'
              ' no matter what state',
        responseMessages=[
            {
                "code": 200,
                "message": "Simulations retrieved successfully"
            }
        ]
    )
    @marshal_with(Simulation.resource_fields)
    def get(self):
        """
        Gets the list of simulations
        """
        return simulations, 200
