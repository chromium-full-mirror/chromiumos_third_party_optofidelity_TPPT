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

from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
from TPPTcommon.TestStep import TestStep
from TPPTcommon.grid import create_stationary_jitter_static_noise_grid, GridVisContainer
from MeasurementDB import *
# Logging module is needed if script wants to send logging
# information to the debug window.
import logging
import time
logger = logging.getLogger(__name__)

# Database table name for the test case.
DB_TEST_TABLE_NAME = 'stationary_jitter_static_noise_test'

# Database table name for the test results.
DB_RESULTS_TABLE_NAME = 'stationary_jitter_static_noise_results'

# Database table indices associated with test case.
DB_TABLE_INDICES = [[DB_TEST_TABLE_NAME, 'test_id'], [DB_RESULTS_TABLE_NAME, 'point_id']]



class StationaryJitterStaticNoiseTest(Base):

    # Test is defined here
    __tablename__ = DB_TEST_TABLE_NAME

    id = Column( Integer, primary_key = True )
    test_id = Column( Integer, ForeignKey('test_item.id', ondelete='CASCADE'), nullable=False )
    test = relation( TestItem, backref = backref(DB_TEST_TABLE_NAME, order_by = id) )

    # test_type is used in analysis the choose correct pass/fail criteria for the test
    test_type = Column(Text) # default_stationary_jitter, noise_test

    # Robot tap position
    robot_x = Column( Float )
    robot_y = Column( Float )

    border_width = Column(Float)

    finger_name = Column(Text)
    finger_type = Column(Text)
    finger_size = Column(Float)
    finger2_name = Column(Text)
    separation = Column(Float)

    lift_off_distance = Column(Float)
    step_size = Column(Float)
    ground_status = Column(Text) # "ground" or "low_ground"
    noise_status = Column(Text) # charger name
    display_background = Column(Text)
    touch_area = Column(Text) # "edge_area" or "center_area"
    contact_duration = Column(Float) # duration in ms
    number_of_fingers_on_screen = Column(Integer)


class StationaryJitterStaticNoiseResults(Base):

    # Results are defined here
    __tablename__ = DB_RESULTS_TABLE_NAME

    id = Column( Integer, primary_key = True )
    point_id = Column( Integer, ForeignKey(DB_TEST_TABLE_NAME + '.id', ondelete='CASCADE'), nullable=False )
    point = relation( StationaryJitterStaticNoiseTest, backref = backref(DB_RESULTS_TABLE_NAME, order_by = id) )

    panel_x = Column( Float )
    panel_y = Column( Float )
    sensitivity = Column( Float )
    delay = Column( Float )
    finger_id = Column( Integer )
    time = Column( Float )
    event = Column( Integer )

class StationaryJitterStaticNoise(TestStep):
    """
    In this test case DUT surface is tapped at regular grid locations with specific duration for reach tap.
    Touch results are analyzed for jitter and  in TPPT analysis.
    Edge and center area can be tested with different tips. In this case there can also be
    additional finger touching the panel via the two-finger tool.
    """

    def __init__(self, context):
        """
        The 'init' method mainly defines the test case controls for GUI and is executed when script is loaded.
        """

        super().__init__('Stationary Jitter Static Noise')

        self.context = context

        # If database_configuration is defined, the controls parameters will be overridden from database if possible
        self.database_configuration = StationaryJitterStaticNoiseTestParameters

        test_types = ['', 'default_stationary_jitter', 'noise_test']
        self.controls.test_type = test_types[0]
        self.controls.info['test_type'] = {'label': ' Test type (for pass/fail limits)', 'items': test_types}

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

        self.controls.finger2_name = ""
        self.controls.info['finger2_name'] = {'label': 'Finger 2 name (empty means no tip)', 'items': tip_names + [""]}

        self.controls.separation = 20.0
        self.controls.info['separation'] = {'label': 'Two-finger separation [mm]'}

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
        self.controls.info['border_width'] = {'label': 'Width of the edge area [mm]', 'min': 0}

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
        dut_height = dut.height

        self.context.html("Running Stationary Jitter Static Noise test for dut:%s" % (dut))

        robot = self.context.robot

        # Use test case specific lift-off distance instead of dut.base_distance.
        base_distance = self.controls.lift_off_distance

        separation = self.controls.separation

        if separation > dut_height / 2:
            self.context.html_color("Separation is too large for the DUT. Using shorter separation.", "red")
            separation = dut_height / 2

        # Set finger separation that is used for all points.
        try: # this fails if one is using standard 3-axis simulator
            robot.set_finger_separation(separation)
        except:
            self.context.html_color("Finger separation could not be set", color="red")

        measurement_points = self.create_grid(dut, separation)

        # Create database entry for the test case and execute the item.
        test_item = self.context.create_db_test_item("Stationary Jitter Static Noise Test")

        dut = self.context.get_active_dut()
        tip = self.context.get_active_tip()

        self.context.set_robot_default_speed()
        self.context.clear_dut_points()

        # Start saving the filtered log data
        self.start_kmsg_log()

        for index, point in enumerate(measurement_points):
            # Update indicators in GUI.
            self.context.indicators.set_test_detail('Point', str(index + 1) + ' / ' + str(len(measurement_points)))

            # Create database entry for the point to be measured.
            point_id = self.create_point_id(point, test_item, tip)

            azimuth = point.angle

            # Move over target position.
            dut.move(point.x, point.y, base_distance, azimuth=azimuth)

            # Start continuous measurement and move robot to touch DUT to obtain a stream of touch events.
            # Timeout is used to stop event stream after robot has moved off the surface.
            # With ADB the touch event collection must be started before touch events are reported.
            continuous_measurement = self.context.create_continuous_measurement(None)
            continuous_measurement.point = point
            continuous_measurement.start(3.0)

            # Move to touch the DUT surface.
            dut.move(point.x, point.y, -1.0, azimuth=azimuth)

            # Store touchlist length so that we know the event from the moment the move gesture ended.
            touchlist_len = len(continuous_measurement.parse_data())

            # Sleep for a while to get a good stream of touch values.
            time.sleep(self.controls.contact_duration * 0.001)

            # Get measurement data before moving off DUT to avoid getting garbage data from lift-off.
            touchlist = continuous_measurement.parse_data()

            # Move off DUT surface to end data collection.
            dut.move(point.x, point.y, base_distance, azimuth=azimuth)

            # End measurement.
            continuous_measurement.end()

            # Get touch events. touchlist_len divides the events into two sets:
            # 1) Events from the duration of move gesture and 2) events during contact with no robot movement.
            # Take the last event from set 1 and all events from set 2.
            # This is because some devices have practically no jitter so that set 2 is most often empty.
            # We want to have at least one event in touchlist to indicate that there was no error in the measurement.
            if touchlist_len > 0:
                touchlist = touchlist[touchlist_len - 1:]

            # Save results to database.
            self.save_measurement_data(point_id, touchlist)

            # Check if test should pause or stop.
            self.context.breakpoint()

        # Save the filtered kmsg log entries that were recorded during the measurement
        kmsg_log = self.stop_kmsg_log()

        self.context.close_db_test_item(test_item, kmsg_log)

    def create_grid(self, dut, separation):
        """
        Create grid of points that define the geometry of the test case.
        :param dut: DUT where the grid is evaluated on.
        :param separation: Separation for 2-finger tool.
        """

        return create_stationary_jitter_static_noise_grid(dut, self.controls.step_size,
                                 self.controls.touch_area, self.controls.border_width, separation)

    def visualize_grid(self, dut):
        """
        Construct a visualization of the test case grid.
        :param dut: DUT where the grid is evaluated on.
        """

        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), self.create_grid(dut, self.controls.separation), dut.name)

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
            _ = self.create_grid(dut, self.controls.separation)
            return True
        except Exception as e:
            logger.error(str(e))
            return False

    def create_point_id(self,point, test_item, tip):
        num_fingers = 2 if len(self.controls.finger2_name) > 0 else 1

        test = StationaryJitterStaticNoiseTest()

        test.test_type = self.controls.test_type

        test.robot_x = point.x
        test.robot_y = point.y
        test.border_width = self.controls.border_width
        test.finger_name = self.controls.finger_name
        test.finger_type = self.controls.finger_type
        test.finger_size = self.controls.finger_size
        test.finger2_name = self.controls.finger2_name
        test.separation = self.controls.separation
        test.lift_off_distance = self.controls.lift_off_distance
        test.step_size = self.controls.step_size
        test.ground_status = self.controls.ground_status
        test.noise_status = self.controls.noise_status
        test.display_background = self.controls.display_background
        test.touch_area = self.controls.touch_area
        test.contact_duration = self.controls.contact_duration
        test.number_of_fingers_on_screen = num_fingers

        test.test_id = test_item.id

        self.context.db.add(test)

        return test.id

    def save_measurement_data(self, point_id, touchlist):
        """
        Save measurement to database.
        """
        dblist = []

        for testresult in touchlist:
            results = StationaryJitterStaticNoiseResults()

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
        Save the filtered ksmsg log entries that were recorded during the measurement
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


class StationaryJitterStaticNoiseTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'stationary_jitter_static_noise_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_jitter_configurations')

    enabled = Column(Boolean)

    border_width = Column(DECIMAL(8, 2))
    finger_name = Column(VARCHAR(40))
    finger_type = Column(VARCHAR(40))
    finger_size = Column(DECIMAL(8, 2))
    finger2_name = Column(VARCHAR(40))
    separation = Column(DECIMAL(8, 2))
    step_size = Column(DECIMAL(8, 2))
    display_background = Column(VARCHAR(40))
    lift_off_distance = Column(DECIMAL(8, 2))
    ground_status = Column(VARCHAR(40))
    noise_status = Column(VARCHAR(40))
    touch_area = Column(VARCHAR(40))
    contact_duration = Column(DECIMAL(8, 2))
    test_type = Column(VARCHAR(40))
