"""
Copyright (c) 2019, OptoFidelity OY

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    3. All advertising materials mentioning features or use of this software must display the following acknowledgement: This product includes software developed by the OptoFidelity OY.
    4. Neither the name of the OptoFidelity OY nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
from sqlalchemy import Column, Integer, ForeignKey, Boolean, DECIMAL, VARCHAR
from sqlalchemy.orm import relationship
import numpy as np

from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
from TPPTcommon.TestStep import TestStep
from TPPTcommon.grid import create_grid_accuracy_grid, create_multi_finger_tap_grid, \
                            calculate_multifinger_point, point_dist_to_many_points_avg,\
                            separate_multifinger_events, GridVisContainer
import TPPTcommon.containers as Containers
from MeasurementDB import *
# Logging module is needed if script wants to send logging
# information to the debug window.
import logging

logger = logging.getLogger(__name__)

# Database table name for the test case.
DB_TEST_TABLE_NAME = 'grid_accuracy_test'

# Database table name for the test results.
DB_RESULTS_TABLE_NAME = 'grid_accuracy_results'

# Database table indices associated with test case.
DB_TABLE_INDICES = [[DB_TEST_TABLE_NAME, 'test_id'], [DB_RESULTS_TABLE_NAME, 'point_id']]


class GridAccuracyTest(Base):

    # Test is defined here
    __tablename__ = DB_TEST_TABLE_NAME

    id = Column( Integer, primary_key = True )
    test_id = Column( Integer, ForeignKey('test_item.id', ondelete='CASCADE'), nullable=False )
    test = relation( TestItem, backref = backref(DB_TEST_TABLE_NAME, order_by = id) )

    # Robot tap position
    robot_x = Column( Float )
    robot_y = Column( Float )

    border_width = Column(Float)

    finger_name = Column(Text)
    finger_type = Column(Text)
    finger_size = Column(Float)
    num_fingers = Column(Float)

    lift_off_distance = Column(Float)
    step_size = Column(Float)
    ground_status = Column(Text) # "ground" or "low_ground"
    noise_status = Column(Text)  # charger name
    display_background = Column(Text)
    touch_area = Column(Text) # "edge_area" or "center_area"
    contact_duration = Column(Float) # duration in ms


class GridAccuracyResults(Base):

    # Results are defined here
    __tablename__ = DB_RESULTS_TABLE_NAME

    id = Column( Integer, primary_key = True )
    point_id = Column( Integer, ForeignKey(DB_TEST_TABLE_NAME + '.id', ondelete='CASCADE'), nullable=False )
    point = relation( GridAccuracyTest, backref = backref(DB_RESULTS_TABLE_NAME, order_by = id) )

    panel_x = Column( Float )
    panel_y = Column( Float )
    sensitivity = Column( Float )
    delay = Column( Float )
    finger_id = Column( Integer )
    time = Column( Float )
    event = Column( Integer )

class GridAccuracy(TestStep):
    """
    In this test case DUT surface is tapped at regular grid locations with specific duration for reach tap.
    Touch results are analyzed for grid accuracy in TPPT analysis.
    The center area is tapped with different tips and grounding conditions.
    """

    def __init__(self, context):
        """
        The 'init' method mainly defines the test case controls for GUI and is executed when script is loaded.
        """

        super().__init__('Grid Accuracy')

        self.context = context

        # If database_configuration is defined, the controls parameters will be overridden from database if possible
        self.database_configuration = GridAccuracyTestParameters

        tip_names = [node.name for node in context.tips_node.children]
        # In order to update values we need to be able to change value in dropdown menu
        tip_names.insert(0, '')
        self.controls.finger_name = tip_names[0] if tip_names else ""
        self.controls.info['finger_name'] = {'label': 'Finger name', 'items': tip_names}

        # Not used by test. Follows from finger name and tip properties.
        self.controls.finger_type = "metal"
        self.controls.info['finger_type'] = {'label': 'Finger type'}

        # Not used by test. Follows from finger name and tip properties.
        self.controls.finger_size = 10.0
        self.controls.info['finger_size'] = {'label': 'Finger size [mm]', 'min': 0.0}

        groundings = ['', 'ground', 'low_ground']
        self.controls.ground_status = groundings[0]
        self.controls.info['ground_status'] = {'label': 'Grounding', 'items': groundings}

        self.controls.noise_status = ""
        self.controls.info['noise_status'] = {'label': 'Noise source'}

        self.controls.display_background = ""
        self.controls.info['display_background'] = {'label': 'Display background'}

        touch_areas = ['', 'center_area', 'edge_area']
        self.controls.touch_area = touch_areas[0]
        self.controls.info['touch_area'] = {'label': 'Touch area', 'items': touch_areas}

        self.controls.border_width = 4.0
        self.controls.info['border_width'] = {'label': 'Width of the edge area [mm]', 'min': 0.0}

        self.controls.lift_off_distance = 10.0
        self.controls.info['lift_off_distance'] = {'label': 'Lift-off distance [mm]', 'min': 0.0}

        self.controls.step_size = 2.0
        self.controls.info['step_size'] = {'label': 'Grid step size [mm]', 'min': 0.0}

        self.controls.contact_duration = 100.0
        self.controls.info['contact_duration'] = {'label': 'Contact duration [ms]', 'min': 0.0}

    def execute(self):
        """
        The 'execute' method contains the actual work that the
        test step is doing.
        """

        dut = self.context.get_active_dut()
        tip = self.context.get_active_tip()

        self.context.html("Running Grid Accuracy test for dut:%s" % (dut))

        measurement_points = self.create_grid(dut, tip)

        # Create database entry for the test case and execute the item.
        test_item = self.context.create_db_test_item("Grid Accuracy Test")

        # Use test case specific lift-off distance instead of dut.base_distance.
        base_distance = self.controls.lift_off_distance

        self.context.set_robot_default_speed()
        self.context.clear_dut_points()

        # Start saving the filtered log data
        self.start_kmsg_log()

        for index, point in enumerate(measurement_points):
            # Update indicators in GUI.
            self.context.indicators.set_test_detail('Point', str(index + 1) + ' / ' + str(len(measurement_points)))

            # Move to touch the DUT surface.
            dut.move(point.x, point.y, base_distance, azimuth=point.angle)

            # Start continuous measurement to obtain a stream of touch events.
            # Timeout is used to stop event stream after robot has moved off the surface.
            continuous_measurement = self.context.create_continuous_measurement(None)
            continuous_measurement.point = point

            continuous_measurement.start(3.0)

            # Perform tap gesture.
            dut.tap(point.x, point.y, base_distance, clearance=-1, duration=self.controls.contact_duration * 0.001,
                    azimuth=point.angle)

            # End measurement.
            continuous_measurement.end()

            # Get measurement data that should include touch down and lift-off events.
            touchlist_all = continuous_measurement.parse_data()

            if not tip.is_multifinger:
                # Create database entry for the measured point
                point_id = self.create_point_id(point, test_item)
                # Save results to database.
                self.save_measurement_data(point_id, touchlist_all)
            else: # tip is multifinger
                touchdict_separated = self.process_multitouch(point, touchlist_all)
                # Going through the points in numerical order and saving them to database
                for tip_id in range(len(touchdict_separated)):
                    point_to_save = touchdict_separated[tip_id]['point']
                    touches_to_save = touchdict_separated[tip_id]['touchlist']
                    point_id = self.create_point_id(point_to_save, test_item)
                    self.save_measurement_data(point_id, touches_to_save)
            # Check if test should pause or stop.
            self.context.breakpoint()

        # Save the filtered kmsg log entries that were recorded during the measurement
        kmsg_log = self.stop_kmsg_log()

        self.context.close_db_test_item(test_item, kmsg_log)

    def create_grid(self, dut, tip):
        """
        Create grid of points that define the geometry of the test case.
        :param dut: DUT where the grid is evaluated on.
        :param tip: tip that is used to execute the grid
        """
        if tip.is_multifinger:
            # it is not possible to separate edge areas in multifinger tap
            if self.controls.touch_area != "center_area":
                raise Exception("Multifinger tap only possible in center area")
            grid = create_multi_finger_tap_grid(dut, tip.num_tips, tip.tip_distance)
        else: # tip is not a multifinger
            grid = create_grid_accuracy_grid(dut, self.controls.step_size,
                                             self.controls.touch_area, self.controls.border_width)

        return grid

    def visualize_grid(self, dut):
        """
        Construct a visualization of the test case grid.
        :param dut: DUT where the grid is evaluated on.
        """

        # We need to do some tricks to get the finger information to create grid pattern
        tip = None

        # Information from tip (~tool) is needed to draw the diagram properly and this
        # is probably the easiest way to get the information at this point
        for tip_node in self.context.tips_node.children:
            if tip_node.name == self.controls.finger_name:
                tip = tip_node.tnt_tip
                break

        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), self.create_grid(dut, tip), dut.name)

    def tip_is_valid(self):
        """
        Tries to find the tip by its name.
        :return: True if tip is found, False if not found
        """
        tip = self.context.tips_node.find_by_name(self.controls.finger_name)
        if tip is not None:
            return True
        else:
            return False

    def pattern_is_valid(self):
        """
        Tries to create the measurement grid to see if it is possible
        :return: True if the grid can be created, False if the grid cannot be created
        """
        dut = self.context.get_active_dut()
        tip = self.context.tips_node.find_by_name(self.controls.finger_name)
        try:
            _ = self.create_grid(dut, tip.tnt_tip)
            return True
        except Exception as e:
            logger.error(str(e))
            return False

    def process_multitouch(self, point, touchlist_all):
        '''
        Processes a multifinger touch recording to be compatible with analyses
        -> separates touch events based on finger id, calculates expected tap points
            for all the fingers and then connects the separated touch events to
            respective points
        :param point: the Point object based on which the tap is done
        :param touchlist_all: all the recorded touchevents
        :return: a dict with calculated multifinger points and separated touchlist connected
                to a finger id
        '''
        touch_dict_separated = {}
        # In order to know the multifinger tap points as mm we need info of the dut
        dut_resolution = self.context.get_active_dut_node().resolution
        active_dut = self.context.get_active_dut()
        dut_size = [active_dut.width, active_dut.height]
        # Create skeleton for sorted touches and already add respective points
        for num in range(point.fingers):
            point_calc = calculate_multifinger_point(point, num)
            touch_dict_separated[int(num)] = {"point": point_calc,
                                              "touchlist": []}

        # Separate events from recorded touchlist per finger id
        separated_events = separate_multifinger_events(touchlist_all)

        # Collection for distances between measurement points and robot points
        distances = []  # [point_num, finger_id, distance_avg]

        # Calculate distances between all the robot and measurement points
        for point_num, values in touch_dict_separated.items():
            comparison_point = values["point"]
            # Check average distance to all the possible measurement points
            for finger_id, events in separated_events.items():
                # Separate the coordinates from the complete touch data
                touch_coords = []
                for event in events:
                    x_pix, y_pix = event[0], event[1]
                    # transforming the coordinates from pixels to mm
                    x = x_pix*dut_size[0]/dut_resolution[0]
                    y = y_pix*dut_size[1]/dut_resolution[1]
                    touch_coords.append([x, y])
                distance_avg = point_dist_to_many_points_avg(comparison_point, touch_coords)
                distances.append([point_num, finger_id, distance_avg])

        # Sorting the distances to be sure to connect the closest points
        # and measurement point groups
        sorted_distances = sorted(distances, key=lambda x: x[2])
        # Bookkeeping for robot points that are already assigned their first measurement values
        # and the fingers the values of which are used
        used_points = []
        used_fingers = []
        # Connect each robot point with max one measurement point group.
        for pair in sorted_distances:
            point_num, finger_id = pair[0], pair[1]
            # If the point with smallest distance is already handled we can skip it
            # same applies to fingers
            if point_num in used_points or finger_id in used_fingers:
                continue
            # Adding the measurement events to the point's touchlist
            for event in separated_events[finger_id]:
                touch_dict_separated[point_num]['touchlist'].append(event)
            used_points.append(point_num)  # the point is now handled
            used_fingers.append(finger_id) # the finger is now used

        # Removing the handled finger_ids from the distance "matrix"
        sorted_distances[:] = [x for x in sorted_distances if x[1] not in used_fingers]

        # If something is left, it is assumed to be a ghost finger
        used_fingers = []
        for distance in sorted_distances:
            finger_id = distance[1]
            if finger_id in used_fingers:
                continue
            used_fingers.append(finger_id)
            # Create a dummy point with all coordinates set to None to indicate ghost finger
            ghost_point_num = max(used_points) + 1
            ghost_point = Containers.Point(None, None, None)
            touch_dict_separated[ghost_point_num] = {"point": ghost_point,
                                                     "touchlist": []}
            for event in separated_events[finger_id]:
                touch_dict_separated[ghost_point_num]['touchlist'].append(event)
            used_points.append(ghost_point_num)

        # Make sure that all the touchevents are in timestamp order
        for _, values in touch_dict_separated.items():
            values['touchlist'] = sorted(values['touchlist'], key=lambda i: float(i[5]))

        return touch_dict_separated

    def create_point_id(self, point, test_item):

        test = GridAccuracyTest()

        test.robot_x = point.x
        test.robot_y = point.y
        test.border_width = self.controls.border_width
        test.finger_name = self.controls.finger_name
        test.finger_type = self.controls.finger_type
        test.finger_size = self.controls.finger_size
        test.num_fingers = point.fingers
        test.lift_off_distance = self.controls.lift_off_distance
        test.step_size = self.controls.step_size
        test.ground_status = self.controls.ground_status
        test.noise_status = self.controls.noise_status
        test.display_background = self.controls.display_background
        test.touch_area = self.controls.touch_area
        test.contact_duration = self.controls.contact_duration

        test.test_id = test_item.id

        self.context.db.add(test)

        return test.id

    def save_measurement_data(self, point_id, touchlist):
        """
        Save measurement to database.
        """
        dblist = []

        for testresult in touchlist:
            results = GridAccuracyResults()

            results.panel_x = float(testresult[0])
            results.panel_y = float(testresult[1])
            results.sensitivity = float(testresult[2])
            results.finger_id = int(testresult[3])
            results.delay = testresult[4]
            results.time = testresult[5]
            results.event = testresult[6]
            results.point_id = point_id

            dblist.append(results)

            self.context.add_dut_point(float(testresult[0]), float(testresult[1]))

        self.context.db.addAll(dblist)

    def start_kmsg_log(self):
        '''
        Start reading the Android kmsg log
        :return: Nothing
        '''
        try:
            self.context.start_log()
            self.context.html("Starting to read DUT kmsg log")
        except:
            self.context.html_color("Starting to read kmsg log failed", color="red")
            pass

    def stop_kmsg_log(self):
        '''
        Save the filtered kmsg log entries that were recorded during the measurement
        :return: The log entry if log exists, otherwise empty string
        '''
        try:
            kmsg_log = self.context.stop_log()
            self.context.html("Android kmsg log read successful")
        except:
            kmsg_log = ""
            self.context.html_color("Android kmsg log read failed", color="red")
            pass
        return kmsg_log


class GridAccuracyTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'grid_accuracy_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_grid_accuracy_configurations')

    enabled = Column(Boolean)

    border_width = Column(DECIMAL(8, 2))
    finger_name = Column(VARCHAR(40))
    finger_type = Column(VARCHAR(40))
    finger_size = Column(DECIMAL(8, 2))
    step_size = Column(DECIMAL(8, 2))
    display_background = Column(VARCHAR(40))
    lift_off_distance = Column(DECIMAL(8, 2))
    ground_status = Column(VARCHAR(40))
    noise_status = Column(VARCHAR(40))
    touch_area = Column(VARCHAR(40))
    contact_duration = Column(DECIMAL(8, 2))
