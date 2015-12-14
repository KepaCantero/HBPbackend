"""
This module contains the REST implementation
for loading and saving experiment transfer functions
"""


__author__ = 'Bernd Eckstein'

import os
import tempfile
import shutil
import logging
from flask_restful import Resource, request, fields
from flask_restful_swagger import swagger

from hbp_nrp_backend.rest_server import NRPServicesClientErrorException, \
    NRPServicesGeneralException
from hbp_nrp_backend.rest_server.__UserAuthentication import UserAuthentication
from hbp_nrp_backend.rest_server.__ExperimentService import ErrorMessages, \
    substitute_bibi_transferfunctions

logger = logging.getLogger(__name__)
# pylint: disable=no-self-use


@swagger.model
class TransferFunctionDictionary(object):
    """
    Swagger documentation object
    TransferFunctionDict ... tried to make it look like a dictionary for the swagger doc
    """
    resource_fields = {
        'tf_id_1': str.__name__,
        'tf_id_2': str.__name__,
        'tf_id_n': str.__name__
    }


@swagger.model
@swagger.nested(data=TransferFunctionDictionary.__name__)
class TransferFunctionData(object):
    """
    Swagger documentation object
    Main Data Attribute for parsing convenience on the front-end side.
    """
    resource_fields = {
        'data': fields.Nested(TransferFunctionDictionary.resource_fields)
    }
    required = ['data']


class ExperimentTransferfunctions(Resource):
    """
    The resource to load and save experiment transferfunction files
    """

    @swagger.model
    class _TransferFunction(object):
        """
        The source code of a transfer function in a simple string.
        """
        resource_fields = {
            'transfer_functions': fields.List(fields.String)
        }
        required = ['transfer_functions']

    @swagger.model
    class _Bibi(object):
        """
        Get and Set Experiment BIBI
        Only used for swagger documentation
        """

        resource_fields = {
            'filename': fields.String(),
            'base64': fields.String()
        }
        required = ['base64']

    @swagger.operation(
        notes='Save transfer functions of an experiment to the collab',
        parameters=[
            {
                "name": "transfer_functions",
                "required": True,
                "description": "List of Transferfunctions in Python (list of strings)",
                "paramType": "body",
                "dataType": _TransferFunction.__name__
            },
        ],
        responseMessages=[
            {
                "code": 500,
                "message": ErrorMessages.ERROR_SAVING_FILE_500
            },
            {
                "code": 404,
                "message": ErrorMessages.COLLAB_NOT_FOUND_404
            },
            {
                "code": 400,
                "message": "Transfer functions code should be sent in "
                           "the body under the 'transfer_functions' key"
            },
            {
                "code": 200,
            }
        ]
    )
    def put(self, context_id):
        """
        Save transfer functions of an experiment to the collab.

        :param path context_id: The context UUID of the Collab where the transfer functions
         will be saved
        :<json body json array of string transfer_functions: the transfer functions as python
        :status 500: Error on server: environment variable: 'NRP_MODELS_DIRECTORY' is empty
        :status 500: Error saving file
        :status 404: The collab with the given context ID was not found
        :status 404: The request body is malformed
        :status 200: Success. File written.
        """

        # Done here in order to avoid circular dependencies introduced by the
        # way we __init__ the rest_server module.
        from hbp_nrp_backend.collab_interface.NeuroroboticsCollabClient \
            import NeuroroboticsCollabClient

        body = request.get_json(force=True)
        if (not 'transfer_functions' in body):
            raise NRPServicesClientErrorException(
                "Transfer functions code should be sent in "
                "the body under the 'transfer_functions' key"
            )
        tfs = body['transfer_functions']

        client = NeuroroboticsCollabClient(
            UserAuthentication.get_header_token(request),
            context_id
        )

        bibi_file_path = client.clone_bibi_from_collab_context()
        if bibi_file_path is None:
            raise NRPServicesGeneralException(
                "BIBI configuration file not found in the Collab storage",
                "BIBI not found"
            )

        bibi = substitute_bibi_transferfunctions(bibi_file_path, tfs)
        if tempfile.gettempdir() in bibi_file_path:
            logger.debug(
                "removing the temporary bibi configuration file %s",
                bibi_file_path
            )
            shutil.rmtree(os.path.dirname(bibi_file_path))

        client.save_string_to_file_in_collab(
            bibi,
            client.BIBI_CONFIGURATION_MIMETYPE,
            "recovered_bibi_configuration.xml"
        )

        return 200
