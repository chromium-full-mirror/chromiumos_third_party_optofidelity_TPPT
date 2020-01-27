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
from sqlalchemy import Column, Integer, Boolean, DECIMAL, VARCHAR, ForeignKey
from sqlalchemy.orm import relationship

from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
from TPPTcommon.TestStep import TestStep
from TPPTcommon.grid import create_center_points, create_edge_points, create_corner_points, GridVisContainer
from MeasurementDB import *
from TPPTcommon.containers import Line

# Logging module is needed if script wants to send logging
# information to the debug window.
import logging
logger = logging.getLogger(__name__)

# Database table name for the test case.
DB_TEST_TABLE_NAME = 'one_finger_tapping_repeatability_test'

# Databse table name for the test results.
DB_RESULTS_TABLE_NAME = 'one_finger_tapping_repeatability_results'

# Database table indices associated with test case.
DB_TABLE_INDICES = [[DB_TEST_TABLE_NAME, 'test_id'], [DB_RESULTS_TABLE_NAME, 'point_id']]


class OneFingerTappingRepeatabilityTest(Base):
    # One-finger tap results are defined here
    __tablename__ = DB_TEST_TABLE_NAME

    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('test_item.id', ondelete='CASCADE'), nullable=False)
    test = relation(TestItem, backref=backref(DB_TEST_TABLE_NAME, order_by=id))

    # Common parameters
    robot_x = Column(Float)
    robot_y = Column(Float)
    robot_z = Column(Float)
    point_number = Column(Integer)

    border_width = Column(Float)
    finger_name = Column(Text)
    finger_type = Column(Text)
    finger_size = Column(Float)
    display_background = Column(Text)
    number_of_random_locations_center = Column(Integer)
    number_of_random_locations_edge = Column(Integer)
    number_of_random_locations_corner = Column(Integer)
    number_of_taps_at_each_location = Column(Integer)
    lift_off_distance = Column(Float)
    ground_status = Column(Text)
    noise_status = Column(Text)
    touch_area = Column(Text)


class OneFingerTappingRepeatabilityResults(Base):
    # Results are defined here
    __tablename__ = DB_RESULTS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    point_id = Column(Integer, ForeignKey(DB_TEST_TABLE_NAME + '.id', ondelete='CASCADE'), nullable=False)
    point = relation(OneFingerTappingRepeatabilityTest, backref=backref(DB_RESULTS_TABLE_NAME, order_by=id))

    tap_id = Column(Integer)
    point_number = Column(Integer)
    panel_x = Column(Float)
    panel_y = Column(Float)
    sensitivity = Column(Float)
    delay = Column(Float)
    finger_id = Column(Integer)
    time = Column(Float)
    event = Column(Integer)


class TappingRepeatability(TestStep):
    """
    In repeatability test DUT is tapped at random locations multiple times per location.
    Touch events are used in analysis to inspect how close-by taps at single location are.
    """

    def __init__(self, context):
        """
        The 'init' method mainly defines the test case controls for GUI and is executed when script is loaded.
        """
        super().__init__('Tapping repeatability')
        self.context = context

        # If database_configuration is defined, the controls parameters will be overriden from database if possible
        self.database_configuration = OneFingerTappingRepeatabilityTestParameters

        tip_names = [node.name for node in context.tips_node.children]
        # In order to update values we need to be able to change value in dropdown menu
        tip_names.insert(0, '')
        self.controls.finger_name = tip_names[0] if tip_names else ""
        self.controls.info['finger_name'] = {'label': 'Finger name', 'items': tip_names}

        self.controls.finger_type = 'metal'
        self.controls.info['finger_type'] = {'label': 'Finger type'}

        self.controls.finger_size = 10.0
        self.controls.info['finger_size'] = {'label': 'Finger size [mm]'}

        groundings = ['', 'ground', 'low_ground']
        self.controls.ground_status = groundings[0]
        self.controls.info['ground_status'] = {'label': 'Grounding', 'items': groundings}

        # noise source has to be defined with the name "noise source" for loop sequence
        self.controls.noise_status = ''
        self.controls.info['noise_status'] = {'label': 'Noise source'}

        self.controls.display_background = ''
        self.controls.info['display_background'] = {'label': 'Display background'}

        touch_areas = ['', 'center_area', 'edge_area', 'corner_area']
        self.controls.touch_area = touch_areas[0]
        self.controls.info['touch_area'] = {'label': 'Touch area', 'items': touch_areas}

        self.controls.border_width = 4.0
        self.controls.info['border_width'] = {'label': 'Width of the edge area [mm]', "min": 0.0}

        self.controls.lift_off_distance = 10.0
        self.controls.info['lift_off_distance'] = {'label': 'Lift off distance [mm]', "min": 0.0}

        self.controls.number_of_random_locations_center = 13
        self.controls.info['number_of_random_locations_center'] = {'label': 'Number of random locations in center',
                                                                   "min": 0}

        self.controls.number_of_random_locations_edge = 0  # with edge tests this is random locations per edge
        self.controls.info['number_of_random_locations_edge'] = {'label': 'Number of random locations per edge',
                                                                 "min": 0}

        self.controls.number_of_random_locations_corner = 0  # with corner tests this is per corner
        self.controls.info['number_of_random_locations_corner'] = {'label': 'Number of random locations per corner',
                                                                   "min": 0}

        self.controls.number_of_taps_at_each_location = 32
        self.controls.info['number_of_taps_at_each_location'] = {'label': 'Number of taps at each location', "min": 0}

    def execute(self):
        """
        The 'execute' method contains the actual work that the
        test step is doing.
        """
        dut = self.context.get_active_dut()
        tip = self.context.get_active_tip()

        base_distance = self.controls.lift_off_distance

        # Measurement timeout for tap. This should have some margin.
        tap_timeout = 2 * self.context.get_travel_time(base_distance) + 2.0

        self.context.html("Running One Finger Tapping Repeatability test for dut:%s, tip:%s" % (dut, tip))

        measurement_points = self.create_grid(dut)

        self.execute_test_for_points(base_distance, dut, measurement_points, tap_timeout)

    def execute_test_for_points(self, base_distance, dut, measurement_points, tap_timeout):
        # Create database item for the test.
        test_item = self.context.create_db_test_item("One Finger Tapping Repeatability Test")

        # Start saving the filtered log data
        self.start_kmsg_log()

        for point_index, point in enumerate(measurement_points):
            # Move over tap location. This might be far away from current location.
            # This makes sure that measurement timeout appropriately describes the tap gesture.
            dut.move(point.x, point.y, base_distance)

            num_of_taps = self.controls.number_of_taps_at_each_location

            point_number = point_index + 1  # for legacy reasons

            point_id = self.create_point_id(point, point_number, test_item)

            for tap in range(num_of_taps):
                # Update test indicators in GUI.
                tap_info = str(tap + 1) + ' / ' + str(num_of_taps)
                point_info = str(point_number) + ' / ' + str(len(measurement_points))
                self.context.indicators.set_test_details([('Tap', tap_info), ('Point', point_info)])

                tap_measurement = self.context.create_continuous_measurement(None)
                tap_measurement.point = point
                tap_measurement.start(timeout=tap_timeout)

                # Tap DUT at current test location.
                dut.tap(point.x, point.y, z=base_distance, clearance=-1)

                # End measuring tap event.
                tap_measurement.end()
                touch_list = tap_measurement.parse_data()

                logger.debug("execute touch events: {}".format(touch_list))

                # Save tap measurement to database.
                self.save_measurement_data(touch_list, point_id, point_number, tap)

                # Check if test should pause or stop.
                self.context.breakpoint()

        # Save the filtered kmsg log entries that were recorded during the measurement
        kmsg_log = self.stop_kmsg_log()

        self.context.close_db_test_item(test_item, kmsg_log)

    def create_grid(self, dut):
        """
        Create grid of points that define the geometry of the test case.
        :param dut: DUT where the grid is evaluated on.
        """
        if self.controls.touch_area == 'center_area':
            grid_points = create_center_points(dut, self.controls.number_of_random_locations_center,
                                               self.controls.border_width)
        elif self.controls.touch_area == 'edge_area':
            grid_points = create_edge_points(dut, self.controls.number_of_random_locations_edge,
                                             self.controls.border_width)
        elif self.controls.touch_area == 'corner_area':
            grid_points = create_corner_points(dut, self.controls.number_of_random_locations_corner,
                                               self.controls.border_width)
        else:
            raise Exception('Invalid touch area "' + self.controls.touch_area + '"')

        return grid_points

    def visualize_grid(self, dut):
        """
        Construct a visualization of the test case grid.
        :param dut: DUT where the grid is evaluated on.
        """

        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), self.create_grid(dut), dut.name)

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
        try:
            _ = self.create_grid(dut)
            return True
        except Exception as e:
            logger.error(str(e))
            return False



    def create_point_id(self, robot_point, point_number, tap_test_item):
        """
        Save repeatability measurement to database.
        """
        test_results = OneFingerTappingRepeatabilityTest()

        test_results.test_id = tap_test_item.id
        test_results.robot_x = robot_point.x
        test_results.robot_y = robot_point.y
        test_results.robot_z = 0.0
        test_results.point_number = point_number

        test_results.border_width = self.controls.border_width
        test_results.finger_name = self.controls.finger_name
        test_results.finger_type = self.controls.finger_type
        test_results.finger_size = self.controls.finger_size
        test_results.display_background = self.controls.display_background

        test_results.number_of_random_locations_center = self.controls.number_of_random_locations_center
        test_results.number_of_random_locations_edge = self.controls.number_of_random_locations_edge
        test_results.number_of_random_locations_corner = self.controls.number_of_random_locations_corner
        test_results.number_of_taps_at_each_location = self.controls.number_of_taps_at_each_location

        test_results.lift_off_distance = self.controls.lift_off_distance
        test_results.ground_status = self.controls.ground_status
        test_results.touch_area = self.controls.touch_area
        test_results.noise_status = self.controls.noise_status

        self.context.db.add(test_results)

        return test_results.id

    def save_measurement_data(self, measured_point_data, point_id, point_number, tap):
        """
        Save repeatability measurement to database.
        """

        dblist = []

        for testresult in measured_point_data:
            results = OneFingerTappingRepeatabilityResults()

            results.panel_x = float(testresult[0])
            results.panel_y = float(testresult[1])
            results.sensitivity = float(testresult[2])
            results.finger_id = int(testresult[3])
            results.delay = testresult[4]
            results.time = testresult[5]
            results.event = testresult[6]
            results.point_id = point_id
            results.point_number = point_number
            results.tap_id = tap

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


class OneFingerTappingRepeatabilityTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'tapping_repeatability_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    enabled = Column(Boolean)
    border_width = Column(DECIMAL(8, 2))
    finger_name = Column(VARCHAR(40))
    finger_type = Column(VARCHAR(40))
    finger_size = Column(DECIMAL(8, 2))
    display_background = Column(VARCHAR(40))
    number_of_random_locations_center = Column(DECIMAL(8, 2))
    number_of_random_locations_edge = Column(DECIMAL(8, 2))
    number_of_random_locations_corner = Column(DECIMAL(8, 2))
    number_of_taps_at_each_location = Column(DECIMAL(8, 2))  # number or taps at each location
    lift_off_distance = Column(DECIMAL(8, 2))
    ground_status = Column(VARCHAR(40))  # ground, low_ground
    touch_area = Column(VARCHAR(40))  # center_area, edge_area
    noise_status = Column(VARCHAR(40))
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))

    _test_configuration_orm = relationship('TestConfiguration', back_populates='_tapping_repeatability_configurations')
