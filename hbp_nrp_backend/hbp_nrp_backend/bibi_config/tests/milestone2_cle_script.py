# -*- coding: utf-8 -*-
"""
This file is generated. The original demo script this file is based on has been created by Lorenzo Vannucci
meanwhile the Template has been created by Georg Hinkel.
"""
# pragma: no cover

__author__ = 'BIBI Configuration Script'

import rospy
from gazebo_msgs.srv import SpawnModel
from geometry_msgs.msg import Point, Pose, Quaternion
from os.path import expanduser
import os


def cle_function(world_file):

    from hbp_nrp_cle.cle.ROSCLEServer import ROSCLEServer

    # Create ROS server
    cle_server = ROSCLEServer()
    update_progress_function = lambda subtask, update_progress: cle_server.notify_current_task(subtask, update_progress, True)

    cle_server.notify_start_task("Initializing the Neurorobotic Close Loop Engine",
                              "Importing needed packages",
                              5, # number of subtasks
                              True)  # block_ui

    from hbp_nrp_cle.cle.SerialClosedLoopEngine import SerialClosedLoopEngine
    
    from hbp_nrp_cle.robotsim.GazeboLoadingHelper import load_gazebo_model_file, empty_gazebo_world, load_gazebo_world_file
    from hbp_nrp_cle.robotsim.RobotInterface import Topic
    from hbp_nrp_cle.robotsim.RosControlAdapter import RosControlAdapter
    from hbp_nrp_cle.robotsim.RosCommunicationAdapter import RosCommunicationAdapter

    from hbp_nrp_cle.brainsim.PyNNControlAdapter import PyNNControlAdapter
    from hbp_nrp_cle.brainsim.PyNNCommunicationAdapter import PyNNCommunicationAdapter

    import hbp_nrp_cle.tf_framework as nrp

    # Needed in order to cleanup global static variables
    nrp.start_new_tf_manager()

    # import dependencies from BIBI configuration
    
    import geometry_msgs.msg #import Twist
    
    import hbp_nrp_cle.tf_framework.tf_lib #import detect_red
    
    import sensor_msgs.msg #import Image
    

    # import transfer functions specified in Python
    

    
    
    @nrp.MapSpikeSink("left_wheel_neuron", nrp.brain.actors[0], nrp.leaky_integrator_alpha)
    @nrp.MapSpikeSink("right_wheel_neuron", nrp.brain.actors[1], nrp.leaky_integrator_alpha)
    @nrp.Neuron2Robot(Topic('/husky/cmd_vel', geometry_msgs.msg.Twist))
    def linear_twist(t, left_wheel_neuron, right_wheel_neuron):
        
        
        
        return geometry_msgs.msg.Twist(linear=geometry_msgs.msg.Vector3(x=100.0 * min(left_wheel_neuron.voltage, right_wheel_neuron.voltage), y=0.0, z=0.0), angular=geometry_msgs.msg.Vector3(x=0.0, y=0.0, z=300.0 * (left_wheel_neuron.voltage - right_wheel_neuron.voltage)))

    
    @nrp.MapRobotSubscriber("camera", Topic('/husky/camera', sensor_msgs.msg.Image))
    @nrp.MapSpikeSource("red_left_eye", nrp.brain.sensors[slice(0, 3, 2)], nrp.poisson)
    @nrp.MapSpikeSource("red_right_eye", nrp.brain.sensors[slice(1, 4, 2)], nrp.poisson)
    @nrp.MapSpikeSource("green_blue_eye", nrp.brain.sensors[4], nrp.poisson)
    @nrp.Robot2Neuron()
    def eye_sensor_transmit(t, camera, red_left_eye, red_right_eye, green_blue_eye):
        image_results = hbp_nrp_cle.tf_framework.tf_lib.detect_red(image=camera.value)
        
        red_left_eye.rate = 1000.0 * image_results.left
        red_right_eye.rate = 1000.0 * image_results.right
        green_blue_eye.rate = 1000.0 * image_results.go_on
        
        


    # consts
    TIMESTEP = 0.01
    MAX_SIM_TIME = 5

    update_progress_function("Reseting Gazebo robotic simulator", True)
    empty_gazebo_world(update_progress_function)

    cle_server.notify_current_task("Loading experiment environment",
                                True,  # update_progress
                                True)  # block_ui
    load_gazebo_world_file(world_file, update_progress_function)

    # Create interfaces to Gazebo
    cle_server.notify_current_task("Loading neuRobot",
                                True,  # update_progress
                                True)  # block_ui
    # spawn robot model
    load_gazebo_model_file('robot', 'husky_model/model.sdf')

    # control adapter
    roscontrol = RosControlAdapter()
    # communication adapter
    roscomm = RosCommunicationAdapter()


    # Create interfaces to brain
    cle_server.notify_current_task("Loading neural Simulator NEST",
                                True,  # update_progress
                                True)  # block_ui
    # control adapter
    models_path = os.environ.get('NRP_MODELS_DIRECTORY')
    brainfilepath = 'brain_model/braitenberg.h5'
    if models_path is not None:
        brainfilepath = os.path.join(models_path, brainfilepath)
    braincontrol = PyNNControlAdapter(brainfilepath,
                                      actors=slice(0, 5),
                                      sensors=slice(5, 8))
    # communication adapter
    braincomm = PyNNCommunicationAdapter()


    # Create transfer functions manager
    cle_server.notify_current_task("Connecting neural simulator to neurobot",
                                True,  # update_progress
                                True)  # block_ui
    # tf manager
    tfmanager = nrp.config.active_node
    # set adapters
    tfmanager.robot_adapter = roscomm
    tfmanager.brain_adapter = braincomm


    # Create CLE
    cle = SerialClosedLoopEngine(roscontrol, roscomm, braincontrol, braincomm, tfmanager, TIMESTEP)
    # initialize everything
    cle.initialize()

    # Now that we have everything ready, we could prepare the simulation
    cle_server.prepare_simulation(cle)
    # Loading is completed.
    cle_server.notify_finish_task()
    
    # Main infinite loop (until the ROS stop service is called)
    cle_server.main()

    # Once we do reach this point, the simulation is stopped and we could clean after ourselves.
    cle_server.shutdown()