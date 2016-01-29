"""
ROS wrapper around the CLE
"""
import json
import logging
import threading
import rospy
import math
import numpy

from std_msgs.msg import String
from std_srvs.srv import Empty
from threading import Thread, Event

import textwrap
import re

from RestrictedPython import compile_restricted

# This package comes from the catkin package ROSCLEServicesDefinitions
# in the GazeboRosPackage folder at the root of this CLE repository.
from cle_ros_msgs import srv
from hbp_nrp_cle.common import SimulationFactoryCLEError
from hbp_nrp_cleserver.server import ROS_CLE_NODE_NAME, SERVICE_SIM_START_ID, \
    TOPIC_STATUS, TOPIC_TRANSFER_FUNCTION_ERROR, \
    SERVICE_SIM_PAUSE_ID, SERVICE_SIM_STOP_ID, SERVICE_SIM_RESET_ID, SERVICE_SIM_STATE_ID, \
    SERVICE_GET_TRANSFER_FUNCTIONS, SERVICE_SET_TRANSFER_FUNCTION, \
    SERVICE_DELETE_TRANSFER_FUNCTION, SERVICE_GET_BRAIN, SERVICE_SET_BRAIN
from hbp_nrp_cleserver.server.ROSCLEState import InitialState, PausedState
from hbp_nrp_cleserver.server import ros_handler
import hbp_nrp_cle.tf_framework as tf_framework
from hbp_nrp_cle.tf_framework import TFLoadingException
import base64
from tempfile import NamedTemporaryFile

__author__ = "Lorenzo Vannucci, Stefan Deser, Daniel Peppicelli"
logger = logging.getLogger(__name__)


# from http://stackoverflow.com/questions/12435211/
#             python-threading-timer-repeat-function-every-n-seconds
class DoubleTimer(Thread):
    """
    Timer that runs two functions, one every n1 seconds and the other
    every n2 seconds, using only one thread
    """

    def __init__(self, interval1, callback1, interval2, callback2):
        """
        Construct the timer. To make it work properly, interval2 must be a
        multiple of interval1.

        :param interval1: the time interval of the first function
        :param callback1: the first function to be called
        :param interval2: the time interval of the second function
        :param callback2: the second function to be called
        """
        Thread.__init__(self)
        self.setDaemon(True)
        if interval1 <= 0 or interval2 <= 0:
            logger.error("interval1 or interval2 must be positive")
            raise ValueError("interval1 or interval2 must be positive")
        if math.fmod(interval2, interval1) > 1e-10:
            logger.error("interval2 of Double timer is not a multiple \
                          of interval1")
            raise ValueError("interval2 is not a multiple of interval1")
        self.interval1 = interval1
        self.callback1 = callback1
        self.interval2 = interval2
        self.callback2 = callback2
        self.stopped = Event()
        self.stopped.clear()
        self.counter = 0
        self.expiring = False

    def run(self):
        """
        Exec the function and restart the timer.
        """
        while not self.stopped.wait(self.interval1):
            self.callback1()
            if self.expiring:
                self.counter += 1
                if self.counter >= self.interval2 / self.interval1:
                    self.counter = 0
                    self.expiring = False
                    self.callback2()

    def is_expiring(self):
        """
        Return True if the second callback is active, False otherwise.
        """
        return self.expiring

    def cancel_all(self):
        """
        Cancel the timer.
        """
        self.disable_second_callback()
        self.stopped.set()

    def enable_second_callback(self):
        """
        Enable calling of the second callback (one call only).
        """
        self.expiring = True

    def disable_second_callback(self):
        """
        Disable calling of the second callback and reset its timer.
        """
        self.expiring = False
        self.counter = 0

    def get_remaining_time(self):
        """
        Get remaining time before the second callback is executed.
        If the callback is disabled, the function will return the full
        interval2.

        :return: the remaining time before the callback
        """
        if not self.expiring:
            return self.interval2
        else:
            return self.interval2 - self.counter * self.interval1


# pylint: disable=R0902
# the attributes are reasonable in this case
class ROSCLEServer(object):
    """
    A ROS server wrapper around the Closed Loop Engine.
    """
    STATUS_UPDATE_INTERVAL = 1.0

    def __init__(self, sim_id):
        """
        Create the wrapper server

        :param sim_id: The simulation id
        """

        # ROS allows multiple calls to init_node, as long as
        # the arguments are the same.
        rospy.init_node(ROS_CLE_NODE_NAME)

        self.__event_flag = threading.Event()
        self.__event_flag.clear()
        self.__done_flag = threading.Event()
        self.__done_flag.clear()
        self.__state = InitialState(self)

        self.__service_start = None
        self.__service_pause = None
        self.__service_stop = None
        self.__service_reset = None
        self.__service_state = None
        self.__service_get_transfer_functions = None
        self.__service_set_transfer_function = None
        self.__service_delete_transfer_function = None
        self.__service_get_brain = None
        self.__service_set_brain = None
        self.__cle = None

        self.__simulation_id = sim_id
        self.__ros_status_pub = rospy.Publisher(
            TOPIC_STATUS,
            String,
            queue_size=10  # Not expecting more that 10hz
        )
        self.__ros_tf_error_pub = rospy.Publisher(
            TOPIC_TRANSFER_FUNCTION_ERROR,
            SimulationFactoryCLEError,
            queue_size=10  # Not expecting more that 10hz
        )

        self.__current_task = None
        self.__current_subtask_count = 0
        self.__current_subtask_index = 0

        # timeout stuff
        self.__timeout = None
        self.__double_timer = None
        self.start_thread = None

        # Start another thread calling rospy.spin
        # This line has been put here because it has to be called before prepare_simulation,
        # where all the 'rospy.Service's are initialized.
        # This is the best place I managed to found, as it doesn't seem to hurt anybody.
        # Any enhancement is warmly welcomed.
        rospy_thread = threading.Thread(target=rospy.spin)
        rospy_thread.setDaemon(True)
        rospy_thread.start()

    def set_state(self, state):
        """
        Sets the current state of the ROSCLEServer. This is used from the State Pattern
        implementation.
        """
        self.__state = state
        self.__event_flag.set()

    def prepare_simulation(self, cle, timeout=600):
        """
        The CLE will be initialized within this method and ROS services for
        starting, pausing, stopping and resetting are setup here.

        :param __cle: the closed loop engine
        :param timeout: the timeout time of the simulation,
            default is 5 minutes
        """
        self.__cle = cle
        if not self.__cle.is_initialized:
            self.__cle.initialize()

        self.__cle.tfm.publish_error_callback = self.__ros_tf_error_pub.publish

        logger.info("Registering ROS Service handlers")

        # We have to use lambdas here (!) because otherwise we bind to the state which is in place
        # during the time we set the callback! I.e. we would bind directly to the initial state.
        # The x parameter is defined because of the architecture of rospy.
        # rospy is expecting to have handlers which takes two arguments (self and x). The
        # second one holds all the arguments sent through ROS (defined in the srv file).
        # Even when there is no input argument for the service, rospy requires this.

        # pylint: disable=unnecessary-lambda
        self.__service_start = rospy.Service(
            SERVICE_SIM_START_ID(self.__simulation_id), Empty,
            lambda x: self.__state.start_simulation()
        )

        self.__service_pause = rospy.Service(
            SERVICE_SIM_PAUSE_ID(self.__simulation_id), Empty,
            lambda x: self.__state.pause_simulation()
        )

        self.__service_stop = rospy.Service(
            SERVICE_SIM_STOP_ID(self.__simulation_id), Empty,
            lambda x: self.__state.stop_simulation()
        )

        self.__service_reset = rospy.Service(
            SERVICE_SIM_RESET_ID(self.__simulation_id), srv.ResetSimulation,
            lambda x: self.__state.reset_simulation(x)
        )

        self.__service_state = rospy.Service(
            SERVICE_SIM_STATE_ID(self.__simulation_id), srv.GetSimulationState,
            lambda x: str(self.__state)
        )

        self.__service_get_transfer_functions = rospy.Service(
            SERVICE_GET_TRANSFER_FUNCTIONS(self.__simulation_id), srv.GetTransferFunctions,
            self.__get_transfer_function_sources
        )

        self.__service_set_transfer_function = rospy.Service(
            SERVICE_SET_TRANSFER_FUNCTION(self.__simulation_id), srv.SetTransferFunction,
            self.__set_transfer_function
        )

        self.__service_delete_transfer_function = rospy.Service(
            SERVICE_DELETE_TRANSFER_FUNCTION(self.__simulation_id), srv.DeleteTransferFunction,
            self.__delete_transfer_function
        )

        self.__service_get_brain = rospy.Service(
            SERVICE_GET_BRAIN(self.__simulation_id), srv.GetBrain,
            self.__get_brain
        )

        self.__service_set_brain = rospy.Service(
            SERVICE_SET_BRAIN(self.__simulation_id), srv.SetBrain,
            self.__set_brain
        )

        self.__timeout = timeout
        self.__double_timer = DoubleTimer(
            self.STATUS_UPDATE_INTERVAL,
            self.__publish_state_update,
            self.__timeout,
            self.quit_by_timeout
        )
        self.__double_timer.start()
        self.start_timeout()

    def __get_remaining(self):
        """
        Get the remaining time of the simulation
        """
        return self.__double_timer.get_remaining_time()

    # pylint: disable=unused-argument, no-self-use
    def __get_brain(self, request):
        """
        Returns the current neuronal network model. By default we
        do assume that if the sources are not available, the model
        comes from a h5 file. This has to be refined once we will
        be more confident in the fate of the h5 files.

        :param request: The rospy request parameter
        :return: an array compatible with the GetBrain.srv ROS service
        """
        braintype = "h5"
        data_type = "base64"
        brain_code = "N/A"
        if tf_framework.get_brain_source():
            braintype = "py"
            data_type = "text"
            brain_code = tf_framework.get_brain_source()

        return [
            braintype,
            brain_code,
            data_type,
            json.dumps(tf_framework.get_brain_populations())
        ]

    def __set_brain(self, request):
        """
        Sets the neuronal network according to the given request

        :param request: The mandatory rospy request parameter
        """
        try:
            if not isinstance(self.__state, InitialState) and \
                    not isinstance(self.__state, PausedState):
                self.__state.pause_simulation()
            with NamedTemporaryFile(prefix='brain', suffix='.' + request.brain_type, delete=False)\
                    as tmp:
                with tmp.file as brain_file:
                    if request.data_type == "text":
                        brain_file.write(request.brain_data)
                    elif request.data_type == "base64":
                        brain_file.write(base64.decodestring(request.brain_data))
                    else:
                        tmp.delete = True
                        return ["Data type {0} is invalid".format(request.data_type), 0, 0]
                self.__cle.load_network_from_file(tmp.name, json.loads(request.brain_populations))
            return ["", 0, 0]
        except ValueError, e:
            return ["Population format is invalid: " + str(e), 0, 0]
        except SyntaxError, e:
            return ["The new brain could not be parsed: " + str(e), e.lineno, e.offset]
        except Exception, e:
            return ["Error changing neuronal network: " + str(e), 0, 0]

    # pylint: disable=unused-argument
    @staticmethod
    def __get_transfer_function_sources(request):
        """
        Return the source code of the transfer functions

        :param request: The mandatory rospy request parameter
        """
        tfs = tf_framework.get_transfer_functions()
        arr = numpy.asarray([tf.source.encode('UTF-8') for tf in tfs])
        return arr

    def __set_transfer_function(self, request):
        """
        Patch a transfer function

        :param request: The mandatory rospy request parameter
        :return: empty string for a successful compilation in restricted mode
                (executed synchronously),
                 an error message otherwise.
        """

        original_name = request.transfer_function_name
        # Delete synchronously the original if needed
        if original_name:
            tf_framework.delete_transfer_function(original_name)

        # Update transfer function's source code
        new_source = textwrap.dedent(request.transfer_function_source)

        # Check whether the function has a single definition name
        logger.debug(
            "About to compile transfer function originally named "
            + original_name + "\n"
            + "with the following python code: \n"
            + repr(new_source)
        )
        m = re.findall(r"def\s+(\w+)\s*\(", new_source)
        if len(m) != 1:
            error_msg = original_name
            if len(m) == 0:
                error_msg += " has no definition name."
            else:
                error_msg += " has multiple definition names."
            error_msg += " Compilation aborted"
            msg = SimulationFactoryCLEError(
                "Transfer Function",
                "NoOrMultipleNames",
                error_msg,
                original_name)
            self.__ros_tf_error_pub.publish(msg)
            return msg.message

        # Compile (synchronously) transfer function's new code in restricted mode
        new_name = m[0]
        new_code = None
        try:
            new_code = compile_restricted(new_source, '<string>', 'exec')
        except SyntaxError as e:
            message = "Syntax Error while compiling the updated" \
                + " transfer function named " + new_name \
                + " in restricted mode.\n" \
                + str(e)
            logger.error(message)
            msg = SimulationFactoryCLEError(
                "Transfer Function",
                "Compile",
                str(e),
                new_name,
                e.lineno,
                e.offset,
                e.text,
                e.filename
            )
            self.__ros_tf_error_pub.publish(msg)
            return message

        # Make sure CLE is stopped. If already stopped, these calls are harmless.
        # (Execution of updated code is asynchronous)
        self.__cle.stop()
        try:
            tf_framework.set_transfer_function(new_source, new_code, new_name)
        except TFLoadingException as e:
            tf_error = SimulationFactoryCLEError(
                "Transfer Function",
                "Loading",
                e.message,
                e.tf_name
            )
            self.__ros_tf_error_pub.publish(tf_error)

        return ""

    def __delete_transfer_function(self, request):
        """
        Delete an existing transfer function

        :param request: The mandatory rospy request parameter
        :return: always True as this command is executed asynchronously.
                 ROS forces us to return a value.
        """
        self.__cle.stop()
        tf_framework.delete_transfer_function(request.transfer_function_name)

        return True

    def start_timeout(self):
        """
        Start the timeout on the current simulation
        """
        self.__double_timer.enable_second_callback()
        logger.info("Simulation will timeout in %f seconds", self.__timeout)

    def stop_timeout(self):
        """
        Stop the timeout
        """
        if self.__double_timer.is_expiring:
            self.__double_timer.disable_second_callback()
            logger.info("Timeout stopped")

    def quit_by_timeout(self):
        """
        Stops the simulation
        """
        self.__state.stop_simulation()
        logger.info("Force quitting the simulation")

    def __publish_state_update(self):
        """
        Publish the state and the remaining timeout
        """
        message = {
            'state': str(self.__state),
            'timeout': self.__get_remaining(),
            'simulationTime': int(self.__cle.simulation_time),
            'realTime': int(self.__cle.real_time),
            'transferFunctionsElapsedTime': self.__cle.tf_elapsed_time(),
            'brainsimElapsedTime': self.__cle.brainsim_elapsed_time(),
            'robotsimElapsedTime': self.__cle.robotsim_elapsed_time()
        }
        logger.info(json.dumps(message))
        self.__ros_status_pub.publish(json.dumps(message))

    def run(self):
        """
        This method implements the main logic of ROSCLEServer.
        It loops, executing and consuming callbacks from a list, which is filled by ROS service
        handlers, until the simulation is not stopped (i.e. its state is set to Stopped).
        """

        while not self.__state.is_final_state():
            self.__event_flag.wait()  # waits until an event is set
            self.__event_flag.clear()

        self.__publish_state_update()
        logger.info("Finished main loop")

    def shutdown(self):
        """
        Unregister every ROS services and topics
        """
        self.__double_timer.join()
        logger.info("Shutting down start service")
        self.__service_start.shutdown()
        logger.info("Shutting down pause service")
        self.__service_pause.shutdown()
        logger.info("Shutting down stop service")
        self.__service_stop.shutdown()
        logger.info("Shutting down reset service")
        self.__service_reset.shutdown()
        logger.info("Shutting down state service")
        self.__service_state.shutdown()
        logger.info("Shutting down get_transfer_functions service")
        self.__service_get_transfer_functions.shutdown()
        logger.info("Shutting down set_transfer_function service")
        self.__service_set_transfer_function.shutdown()
        logger.info("Shutting down get_brain service")
        self.__service_get_brain.shutdown()
        logger.info("Shutting down set_brain service")
        self.__service_set_brain.shutdown()
        logger.info("Unregister error/transfer_function topic")
        self.__ros_tf_error_pub.unregister()
        self.__cle.shutdown()
        self.notify_finish_task()
        logger.info("Unregister status topic")
        self.__ros_status_pub.unregister()

    def notify_start_task(self, task_name, subtask_name, number_of_subtasks, block_ui):
        """
        Sends a status notification that a task starts on the ROS status topic.
        This method will save the task name and the task size in class members so that
        it could be reused in subsequent call to the notify_current_task method.

        :param: task_name: Title of the task (example: initializing experiment).
        :param: subtask_name: Title of the first subtask. Could be empty
                (example: loading Virtual Room).
        :param: number_of_subtasks: Number of expected subsequent calls to
                notify_current_task(_, True, _).
        :param: block_ui: Indicate that the client should block any user interaction.
        """
        if self.__current_task is not None:
            logger.warn(
                "Previous task was not closed properly, closing it now.")
            self.notify_finish_task()
        self.__current_task = task_name
        self.__current_subtask_count = number_of_subtasks
        message = {'progress': {'task': task_name,
                                'subtask': subtask_name,
                                'number_of_subtasks': number_of_subtasks,
                                'subtask_index': self.__current_subtask_index,
                                'block_ui': block_ui}}
        self.__ros_status_pub.publish(json.dumps(message))

    def notify_current_task(self, new_subtask_name, update_progress, block_ui):
        """
        Sends a status notification that the current task is updated with a new subtask.

        :param: subtask_name: Title of the first subtask. Could be empty
                (example: loading Virtual Room).
        :param: update_progress: Boolean indicating if the index of the current subtask
                should be updated (usually yes).
        :param: block_ui: Indicate that the client should block any user interaction.
        """
        if self.__current_task is None:
            logger.warn("Can't update a non existing task.")
            return
        if update_progress:
            self.__current_subtask_index += 1
        message = {'progress': {'task': self.__current_task,
                                'subtask': new_subtask_name,
                                'number_of_subtasks': self.__current_subtask_count,
                                'subtask_index': self.__current_subtask_index,
                                'block_ui': block_ui}}
        self.__ros_status_pub.publish(json.dumps(message))

    def notify_finish_task(self):
        """
        Sends a status notification that the current task is finished.
        """
        if self.__current_task is None:
            logger.warn("Can't finish a non existing task.")
            return
        message = {'progress': {'task': self.__current_task,
                                'done': True}}
        self.__ros_status_pub.publish(json.dumps(message))
        self.__current_subtask_count = 0
        self.__current_subtask_index = 0
        self.__current_task = None

    @ros_handler
    def start_simulation(self):
        """
        Handler for the CLE start() call, also used for resuming after pause().
        """
        # The start() is blocking so it has to be called on a separate thread
        self.start_thread = threading.Thread(target=self.__cle.start)
        self.start_thread.setDaemon(True)
        self.start_thread.start()

    @ros_handler
    def pause_simulation(self):
        """
        Handler for the CLE pause() call. Actually call to CLE stop(), as CLE has no real pause().
        """
        # CLE has no explicit pause command, use stop() instead
        self.__cle.stop()

    @ros_handler
    def stop_simulation(self):
        """
        Handler for the CLE stop() call, includes waiting for the current simulation step to finish.
        """
        self.stop_timeout()
        self.__double_timer.cancel_all()
        self.__cle.stop()
        self.start_thread.join(60)
        if self.start_thread.isAlive():
            logger.error("Error while stopping the simulation, impossible to join the simulation "
                         "thread")

    # pylint: disable=broad-except
    def reset_simulation(self, request):
        """
        Handler for the CLE reset() call.

        :param request: the ROS service request message (cle_ros_msgs.srv.ResetSimulation).
        """

        rsr = srv.ResetSimulationRequest
        reset_type = request.reset_type

        try:
            if reset_type == rsr.RESET_ROBOT_POSE:
                self.__cle.reset_robot_pose()
            elif reset_type == rsr.RESET_WORLD:
                self.__cle.reset_world()
            elif reset_type == rsr.RESET_FULL:
                return False, "This feature has not been implemented yet."
            elif reset_type == rsr.RESET_OLD:
                # we have to call the stop function here, otherwise the main thread
                # will not stop executing the simulation loop

                # TODO (Alessandro): not sure if this is still needed, the comment below
                # seems to imply that stop() is already done on reset()
                self.__cle.stop()
                self.stop_timeout()
                # CLE reset() already includes stop() and wait_step()
                self.__cle.reset()
                self.start_timeout()
        except Exception as e:
            return False, str(e)

        return True, ""
