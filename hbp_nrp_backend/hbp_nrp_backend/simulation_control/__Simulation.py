"""
This module contains the simulation class
"""

__author__ = 'GeorgHinkel'

from hbp_nrp_backend.simulation_control.__StateMachine import stateMachine
from flask_restful import fields
from flask_restful_swagger import swagger


@swagger.model
class Simulation(object):
    """
    The data class for simulations
    """
    def __init__(self, sim_id, experiment_id, state='created'):
        """
        Creates a new simulation
        :param sim_id: The simulation id
        :param experiment_id: The experiment id (Path to ExD configuration)
        :param state: The initial state (created by default)
        """
        self.__state = state
        self.__sim_id = sim_id
        self.__experiment_id = experiment_id
        self.__cle = None

    @property
    def experiment_id(self):
        """
        Gets the experiment ID, i.e. the path to the ExD configuration
        """
        return self.__experiment_id

    @property
    def sim_id(self):
        """
        Gets the simulation ID
        """
        return self.__sim_id

    @property
    def state(self):
        """
        Gets the state of the simulation
        """
        return self.__state

    @state.setter
    def state(self, new_state):
        """
        Sets the state of the simulation to the given value
        :param new_state: The new state
        """
        transitions = stateMachine[self.__state]
        if not new_state in transitions:
            raise InvalidStateTransitionException()
        transitions[new_state](self.__sim_id)
        self.__state = new_state

    @property
    def cle(self):
        """
        The CLE for this simulation
        :return: The CLE instance
        """
        return self.__cle

    @cle.setter
    def cle(self, cle):
        """
        Sets the CLE for this simulation
        :param cle: The new CLE
        """
        self.__cle = cle

    resource_fields = {
        'state': fields.String,
        'simulationID': fields.Integer(attribute='sim_id'),
        'experimentID': fields.String(attribute='experiment_id')
    }


class InvalidStateTransitionException(Exception):
    """
    Represents that an invalid state transition was attempted
    """
    pass
