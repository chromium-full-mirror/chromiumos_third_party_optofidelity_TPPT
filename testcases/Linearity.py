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
from sqlalchemy import Column, Integer, Boolean, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
import numpy as np
import TPPTcommon.containers as Containers


from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
from TPPTcommon.TestStep import TestStep

from TPPTcommon.grid import create_nmm_diagonal_lines, create_nmm_vertical_lines, create_nmm_horizontal_lines,\
                            create_multi_swipe_horizontal, create_multi_swipe_vertical, create_multi_swipe_diagonal,\
                            calculate_multifinger_line, line_dist_to_many_points_avg, separate_multifinger_events, \
                            GridVisContainer
from MeasurementDB import *
# Logging module is needed if script wants to send logging
# information to the debug window.
import logging

logger = logging.getLogger(__name__)

# Database table name for the test case.
DB_TEST_TABLE_NAME = 'linearity_test'

# Database table name for the test results.
DB_RESULTS_TABLE_NAME = 'linearity_results'

# Database table indices associated with test case.
DB_TABLE_INDICES = [[DB_TEST_TABLE_NAME, 'test_id'], [DB_RESULTS_TABLE_NAME, 'line_id']]

class LinearityTest(Base):
    # Linearity test is defined here
    __tablename__ = DB_TEST_TABLE_NAME

    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('test_item.id', ondelete='CASCADE'), nullable=False)
    test = relation(TestItem, backref=backref(DB_TEST_TABLE_NAME, order_by=id))

    # Test type is used in analysis to choose correct pass/fail criteria
    test_type = Column(Text) # default_linearity, sensitivity_lower, noise_test_moving

    # For straight lines, start and stop positions are defined
    start_x = Column(Float)
    start_y = Column(Float)
    end_x = Column(Float)
    end_y = Column(Float)

    # Additional metadata for the analysis to use and to pass further
    num_fingers = Column(Float)
    border_width = Column(Float)

    finger_name = Column(Text)
    finger_type = Column(Text)
    finger_size = Column(Float)

    lift_off_distance = Column(Float)
    step_size = Column(Float)
    ground_status = Column(Text)
    noise_status = Column(Text)
    display_background = Column(Text)
    touch_area = Column(Text)  # center/edge
    swipe_speed = Column(Integer)
    swipe_direction = Column(Integer)  # horizontal, vertical or diagonal


class LinearityResults(Base):
    # Linearity results are defined here
    __tablename__ = DB_RESULTS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    line_id = Column(Integer, ForeignKey(DB_TEST_TABLE_NAME + '.id', ondelete='CASCADE'), nullable=False)
    line = relation(LinearityTest, backref=backref(DB_RESULTS_TABLE_NAME, order_by=id))

    panel_x = Column(Float)
    panel_y = Column(Float)
    sensitivity = Column(Float)
    delay = Column(Float)
    finger_id = Column(Integer)
    time = Column(Float)
    event = Column(Integer)


class Linearity(TestStep):
    """
    In Linearity test DUT is swept along set of lines and touch events are collected as continuous stream.
    """

    def __init__(self, context):
        super().__init__('Linearity')
        """
        The 'init' method mainly defines the test case controls for GUI and is executed when script is loaded.
        """

        # TODO: the field for choosing for example dut should be red if the dut gotten from the database is not
        #
        self.context = context

        self.database_configuration = LinearityTestParameters

        test_types = ['','default_linearity', 'sensitivity_lower', 'noise_test_moving']
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

        groundings = ['', 'ground', 'low_ground']
        self.controls.ground_status = groundings[0]
        self.controls.info['ground_status'] = {'label': 'Grounding', 'items': groundings}

        self.controls.noise_status = ""
        self.controls.info['noise_status'] = {'label': 'Noise status'}

        self.controls.display_background = ""
        self.controls.info['display_background'] = {'label': 'Display background'}

        area_types = ['', 'center_area', 'edge_area']
        self.controls.touch_area = area_types[0]
        self.controls.info['touch_area'] = {'label': 'Touch area', 'items': area_types}

        self.controls.border_width = 4.0
        self.controls.info['border_width'] = {'label': 'Width of the edge area [mm]', 'min': 0.0}

        self.controls.lift_off_distance = 10.0
        self.controls.info['lift_off_distance'] = {'label': 'Lift off distance [mm]', 'min': 0.0}

        self.controls.step_size = 2.0
        self.controls.info['step_size'] = {'label': 'Step size [mm]', 'min': 0.0, 'validate': (
            '(^[+]?\d+(?:\.\d+)?(?:[eE][+]\d+)?$)', "Correct format is 'x mm'(eg. 2 or 2.0)")}

        self.controls.swipe_speed = 50.0
        self.controls.info['swipe_speed'] = {'label': 'Swipe speed [mm/s]', 'min': 0.0}

        swipe_directions = ['','horizontal', 'vertical', 'diagonal']
        self.controls.swipe_direction = swipe_directions[0]
        self.controls.info['swipe_direction'] = {'label': 'Swipe direction', 'items': swipe_directions}

    def execute(self):
        """
        The 'execute' method contains the actual work that the
        test step is doing.
        """

        dut = self.context.get_active_dut()
        tip = self.context.get_active_tip()

        speed = self.controls.swipe_speed
        base_distance = dut.base_distance
        lift_of_distance = self.controls.lift_off_distance

        # Swipe gesture uses the same speed also for moving to the start position of the approaching arc. Therefore it
        # takes a long time to reach DUT surface when using slow speeds ( <10mm/s). Radius setting affects this too, as
        # it affects the distance the finger has to travel before touching the DUT surface.
        # Somewhat dynamic start_timeout setting is necessary. Reasoning behind the following formula:
        # 5.0: Reaching the DUT surface takes always a bit of time. At least 5.0s timeout is needed.
        # 150.0 / speed: With regular speeds (e.g. 150mm/s), this adds only 1 second. But with slow speeds, like 5mm/s
        # or even 3mm/s, enough delay is added for a default radius swipe to reach the surface.
        start_timeout = 5.0 + (150.0 / speed)

        self.context.html("Running Linearity test for dut:%s, tip:%s. Swipe direction is %s" %
                          (dut, tip, self.controls.swipe_direction))

        # Create database entry for the test case. Each swipe set is separate test case.
        test_item = self.context.create_db_test_item("Linearity Test")

        # Create swipe lines for current test set.
        measurement_lines = self.create_grid(dut, tip)

        # Start saving the filtered log data
        self.start_kmsg_log()

        for index, line in enumerate(measurement_lines):
            # Update indicators in GUI.
            self.context.indicators.set_test_detail('Line', str(index + 1) + ' / ' + str(len(measurement_lines)))

            # Jump with default speed over the start point of the line to swipe.
            self.context.set_robot_default_speed()
            dut.jump(line.start_x, line.start_y, lift_of_distance, lift_of_distance)

            # The azimuth needs to be rotated before starting the measurement to avoid
            # timeout issues
            azimuth_angle = line.angle
            dut.move(line.start_x, line.start_y, lift_of_distance, azimuth=azimuth_angle)

            # Swipe with specific speed.
            self.context.set_robot_speed(speed)

            # Start capturing a continuous stream of touch events.
            continuous_measurement = self.context.create_continuous_measurement(line)
            continuous_measurement.start(start_timeout=start_timeout)

            # Perform swipe gesture
            # The line.angle assumes that zero is set along x-axis
            dut.swipe(line.start_x, line.start_y, line.end_x, line.end_y, clearance=-1, radius=20,
                      azimuth1=azimuth_angle, azimuth2=azimuth_angle)

            # End measuring touch events.
            continuous_measurement.end()

            # Parse touch event data.
            touchlist_all = continuous_measurement.parse_data()

            # The way how we save data depends on the finger type:
            # - one finger -> save all the data without processing
            # - multifinger -> divide the data based on finger id, calculate
            #   the expected trajectories for all the fingers, and connect the
            #   measurement points to the line that they most likely present
            if not tip.is_multifinger:
                # Create database entry for the line to swipe.
                line_id = self.create_line_id(line, test_item)
                # Save results to database.
                self.save_measurement_data(line_id, touchlist_all)
            else: # tip is a multifinger
                touchdict_separated = self.process_multitouch(tip, line, touchlist_all)
                # Going through the lines in numerical order and saving them to database
                for num in range(tip.num_tips):
                    line_to_save = touchdict_separated[num]['line']
                    touches_to_save = touchdict_separated[num]['touchlist']
                    line_id = self.create_line_id(line_to_save, test_item)
                    self.save_measurement_data(line_id, touches_to_save)


            # Check if test should pause or stop.
            self.context.breakpoint()

        # Save the filtered kmsg log entries that were recorded during the measurement
        kmsg_log = self.stop_kmsg_log()

        self.context.close_db_test_item(test_item, kmsg_log)

    def create_grid(self, dut, tip):
        """
        Create grid of lines that define the geometry of the test case.
        :param dut: DUT where the grid is evaluated on.
        :param pattern: Pattern string that defines sweep line set.
        :param tip: Tip that is used to run the grid, important in multifinger tests
        """

        swipe_direction = self.controls.swipe_direction

        grid_spacing = self.controls.step_size

        # For center area, lines are clipped to border. For edge area unclipped lines are used.
        # This is because analysis needs to find touch down and touch up events in both cases.
        # Analysis has to filter out center points when doing edge area analysis.
        border_width = self.controls.border_width if self.controls.touch_area == "center_area" else 0

        if tip.is_multifinger:
            if swipe_direction == "horizontal":
                return create_multi_swipe_horizontal(dut, tip.num_tips, tip.tip_distance, border_width)
            elif swipe_direction == "vertical":
                return create_multi_swipe_vertical(dut, tip.num_tips, tip.tip_distance, border_width)
            elif swipe_direction == "diagonal":
                return create_multi_swipe_diagonal(dut, tip.num_tips, tip.tip_distance, border_width)
            else: # Swipe direction not defined correctly
                raise Exception("Linearity test: swipe direction not defined correctly")
        else: # tip is not multifinger
            if swipe_direction == "horizontal":
                return create_nmm_horizontal_lines(dut, grid_spacing, border_width)
            elif swipe_direction == "vertical":
                return create_nmm_vertical_lines(dut, grid_spacing, border_width)
            elif swipe_direction == "diagonal":
                return create_nmm_diagonal_lines(dut, grid_spacing, border_width)
            else: # Swipe direction not defined correctly
                raise Exception("Linearity test: swipe direction not defined correctly")

    def visualize_grid(self, dut):
        """
        Construct a visualization of the test case grid.
        :param dut: DUT where the grid is evaluated on.
        """

        tip = self.context.tips_node.find_by_name(self.controls.finger_name)

        test_pattern = self.create_grid(dut, tip.tnt_tip)

        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), test_pattern, dut.name)

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

    def process_multitouch(self, tip, line, touchlist_all):
        '''
        Processes a multifinger touch recording to be compatible with analyses
        -> separates touch events based on finger id, calculates expected trajectories
            for all the lines and then connects the separated touch events to
            respective lines
        :param tip: active tip object
        :param line: the line object based on which the swipe is done
        :param touchlist_all: all the recorded touchevents
        :return: a dict with calculated trajectory and separated touchlist connected
                to a finger id. The touchlist is allowed to have mixed finger_ids but
                the timestamps are in order
        '''
        touch_dict_separated = {}
        # In order to know the multifinger swipe points as mm we need info of the dut
        dut_resolution = self.context.get_active_dut_node().resolution
        active_dut = self.context.get_active_dut()
        dut_size = [active_dut.width, active_dut.height]
        # Create skeleton for sorted touches and already add respective lines
        for num in range(tip.num_tips):
            line_calc = calculate_multifinger_line(line, num)
            touch_dict_separated[num] = {"line": line_calc,
                                         "touchlist": []
                                         }

        # Separate events from recorded touchlist per finger id
        separated_events = separate_multifinger_events(touchlist_all)

        # Collection for distances between measurement points and robot lines
        distances = [] #[line_num, finger_id, distance_avg]
        # Go through each line one by one and calculate the distance between
        # it and measurement points for each finger
        for line_num, values in touch_dict_separated.items():
            comparison_line = values["line"]
            for finger_id, events in separated_events.items():
                # Separate the coordinates from the complete touch data
                touch_coords = []
                for event in events:
                    x_pix, y_pix = event[0], event[1]
                    # transforming the coordinates from pixels to mm
                    x = x_pix * dut_size[0] / dut_resolution[0]
                    y = y_pix * dut_size[1] / dut_resolution[1]
                    touch_coords.append([x, y])
                distance_avg = line_dist_to_many_points_avg(comparison_line, touch_coords)
                distances.append([line_num, finger_id, distance_avg])

        # Sorting the distances to be sure to connect the closest lines
        # and measurement point groups
        sorted_distances = sorted(distances,  key=lambda x: x[2])
        # Bookkeeping for lines that are already assigned their first measurement values
        # and the fingers the values of which are used
        used_lines = []
        used_fingers = []
        # Connect each robot line with max one measurement point group.
        for pair in sorted_distances:
            line_num, finger_id = pair[0], pair[1]
            # If the line with smallest distance is already handled we can skip it
            # same applies to fingers
            if line_num in used_lines or finger_id in used_fingers:
                continue
            # Adding the measurement events to the line's touchlist
            for event in separated_events[finger_id]:
                touch_dict_separated[line_num]['touchlist'].append(event)
            used_lines.append(line_num)  # the line is now handled
            used_fingers.append(finger_id)  # the finger is now used

        # Removing the handled finger_ids from the distance "matrix"
        sorted_distances[:] = [x for x in sorted_distances if x[1] not in used_fingers]

        # In case we have ghost fingers, each line can have more than one
        # finger id connected to it
        used_fingers = []
        for distance in sorted_distances:
            line_num, finger_id = distance[0], distance[1]
            if finger_id in used_fingers:
                continue
            used_fingers.append(finger_id)
            for event in separated_events[finger_id]:
                touch_dict_separated[line_num]['touchlist'].append(event)

        # Sorting the touchlist values to be in timestamp order. This needs to be done
        # because touchevents with different finger_ids can be assigned to one line
        for _, values in touch_dict_separated.items():
            values['touchlist'] = sorted(values['touchlist'], key=lambda i: float(i[5]))

        return touch_dict_separated

    def create_line_id(self, line, test_item):

        linearitytest = LinearityTest()

        linearitytest.test_type = self.controls.test_type

        linearitytest.start_x = line.start_x
        linearitytest.start_y = line.start_y
        linearitytest.end_x = line.end_x
        linearitytest.end_y = line.end_y
        linearitytest.test_id = test_item.id
        linearitytest.num_fingers = line.fingers

        linearitytest.border_width = self.controls.border_width
        linearitytest.finger_name = self.controls.finger_name
        linearitytest.finger_type = self.controls.finger_type
        linearitytest.finger_size = self.controls.finger_size
        linearitytest.touch_area = self.controls.touch_area
        linearitytest.display_background = self.controls.display_background
        linearitytest.step_size = self.controls.step_size
        linearitytest.swipe_speed = self.controls.swipe_speed
        linearitytest.swipe_direction = self.controls.swipe_direction
        linearitytest.lift_off_distance = self.controls.lift_off_distance
        linearitytest.ground_status = self.controls.ground_status
        linearitytest.noise_status = self.controls.noise_status

        self.context.db.add(linearitytest)

        return linearitytest.id

    def save_measurement_data(self, line_id, touchlist):
        """
        Save linearity measurement to database.
        """

        dblist = []

        for testresult in touchlist:
            testresultlinearity = LinearityResults()

            testresultlinearity.panel_x = float(testresult[0])
            testresultlinearity.panel_y = float(testresult[1])
            testresultlinearity.sensitivity = float(testresult[2])
            testresultlinearity.finger_id = int(testresult[3])
            testresultlinearity.delay = testresult[4]
            testresultlinearity.time = testresult[5]
            testresultlinearity.event = testresult[6]
            testresultlinearity.line_id = line_id
            dblist.append(testresultlinearity)

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


class LinearityTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'linearity_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    enabled = Column(Boolean)
    border_width = Column(DECIMAL(8, 2))
    finger_name = Column(VARCHAR(40))
    finger_type = Column(VARCHAR(40))
    finger_size = Column(DECIMAL(8, 2))
    touch_area = Column(VARCHAR(40))  # edge_area, center_area
    display_background = Column(VARCHAR(40))
    step_size = Column(DECIMAL(8, 2))
    swipe_speed = Column(Integer)
    swipe_direction = Column(VARCHAR(40))  # horizontal, vertical or diagonal
    lift_off_distance = Column(DECIMAL(8, 2))
    ground_status = Column(VARCHAR(40))
    noise_status = Column(VARCHAR(40))
    test_type = Column(VARCHAR(40))

    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))

    _test_configuration_orm = relationship('TestConfiguration', back_populates='_linearity_configurations')
