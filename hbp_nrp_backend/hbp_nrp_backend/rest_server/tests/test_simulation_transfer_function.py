"""
Unit tests for the service that patches transfer function sources
"""

__author__ = 'DanielPeppicelli, LucGuyot'

import hbp_nrp_backend
from hbp_nrp_backend.rest_server import app
from hbp_nrp_backend.rest_server import NRPServicesClientErrorException, NRPServicesTransferFunctionException
from hbp_nrp_backend.simulation_control import simulations, Simulation
from mock import patch, MagicMock
import unittest
import json

class TestSimulationTransferFunction(unittest.TestCase):

    def setUp(self):
        del simulations[:]
        simulations.append(Simulation(0, 'experiment_0', 'default-owner', 'local', 'created'))
        simulations.append(Simulation(1, 'experiment_1', 'untrusted-owner', 'local', 'created'))
        self.sim = simulations[0]
        self.sim.cle = MagicMock()
        self.sim.cle.set_simulation_transfer_function = MagicMock(return_value=True)
        self.client = app.test_client()

    def test_simulation_transfer_function_put(self):
        response = self.client.put('/simulation/0/transfer-functions/incredible_tf_12')
        self.assertEqual(self.sim.cle.set_simulation_transfer_function.call_count, 1)
        self.assertEqual(response.status_code, 200)

        self.sim.cle.set_simulation_transfer_function = MagicMock(return_value=False)
        response = self.client.put('/simulation/0/transfer-functions/stunning_tf_34')
        self.assertRaises(NRPServicesTransferFunctionException)
        self.assertEqual(response.status_code, 400)

        sim = simulations[1]
        response = self.client.put('/simulation/1/transfer-functions/amazing_tf_35')
        self.assertRaises(NRPServicesClientErrorException)
        self.assertEqual(response.status_code, 401)

    def test_simulation_transfer_function_delete(self):
        response = self.client.delete('/simulation/0/transfer-functions/incredible_tf_12')
        self.assertEqual(self.sim.cle.delete_simulation_transfer_function.call_count, 1)
        self.assertEqual(response.status_code, 200)

        self.sim.cle.delete_simulation_transfer_function = MagicMock(return_value=False)
        response = self.client.delete('/simulation/0/transfer-functions/stunning_tf_34')
        self.assertRaises(NRPServicesTransferFunctionException)
        self.assertEqual(response.status_code, 400)

        sim = simulations[1]
        response = self.client.delete('/simulation/1/transfer-functions/amazing_tf_35')
        self.assertRaises(NRPServicesClientErrorException)
        self.assertEqual(response.status_code, 401)

if __name__ == '__main__':
    unittest.main()
