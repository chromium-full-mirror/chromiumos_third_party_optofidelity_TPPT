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
import logging

from abc import ABC, abstractmethod
from collections import namedtuple
from copy import copy, deepcopy
import random

from noise.hp33120a import HP33120A
from TPPTcommon.containers import Line, Point
from TPPTcommon.ConfigurationDatabase import TestConfiguration, ConfigurationDatabase, TestConfigurationGroup
from TPPTcommon.exceptions import GridCreationError, TipSelectionError
from TPPTcommon.grid import GridVisContainer
from TPPTcommon.Node import Node

logger = logging.getLogger(__name__)


class TestStep(Node, ABC):
    def __init__(self, name, context):
        """
        Executed when script is loaded, child classes should define the test case controls for GUI.
        """
        super().__init__(name)
        self.context = context
        self.display_enabled = True
        self.enabled = False
        self.database_configuration = None
        self.results_class = None
        self.measurement_timeout = 2.5
        self.max_gesture_time = 60.0
        self.noise_injection_needed = False
        self.is_manual = False

    def __repr__(self):
        return self.name

    def __deepcopy__(self, memo):
        # Make a "deep" copy that has it's own instance of controls to be able to make configuration combinations
        cls = self.__class__
        step_copy = cls.__new__(cls)
        memo = {id(self): step_copy}
        for key, value in self.__dict__.items():
            if key == 'controls':
                # Currently the objects in the controls do not need to be deeply copied, but this may change if
                # there are lists, dicts, or some such that also need to be independent
                setattr(step_copy, key, copy(value))
            else:
                setattr(step_copy, key, value)

        return step_copy

    def save_test_controls_to_database(self, session, configuration_name, configuration_group):
        if self.database_configuration is not None:
            group_id = session.query(TestConfigurationGroup).filter(TestConfigurationGroup.name == configuration_group).one_or_none().id

            test_configuration_id_result = session.query(TestConfiguration.id) \
                .filter(TestConfiguration.name == configuration_name) \
                .filter(TestConfiguration.configuration_group == group_id).one_or_none()

            if test_configuration_id_result is None:
                test_configuration_id = ConfigurationDatabase.create_and_insert_new_configuration(configuration_group,
                                                                                                  configuration_name,
                                                                                                  session)
            else:
                test_configuration_id = test_configuration_id_result.id

            test_controls = self.controls.get_control_dictionary()
            test_controls['enabled'] = self.enabled

            if not self.database_configuration_exists(session, configuration_group, configuration_name):
                database_object = self.database_configuration()

                for key, value in test_controls.items():
                    if not hasattr(database_object, key):
                        raise AttributeError('No database field for parameter: ' + key)
                    else:
                        setattr(database_object, key, value)

                database_object._test_configuration = test_configuration_id
                session.add(database_object)
            else:
                # The configuration already exists, update the control values
                session.query(self.database_configuration) \
                    .filter(self.database_configuration._test_configuration == test_configuration_id) \
                    .update(test_controls)

    def database_configuration_exists(self, session, group_name, configuration_name):
        group_id = session.query(TestConfigurationGroup).filter(
            TestConfigurationGroup.name == group_name).one_or_none().id

        existing_configuration = session.query(self.database_configuration) \
            .join(self.database_configuration._test_configuration_orm) \
            .filter(TestConfiguration.name == configuration_name) \
            .filter(TestConfiguration.configuration_group == group_id) \
            .one_or_none()

        return True if existing_configuration is not None else False

    def execute(self):
        """
        Tell the robot to perform each gesture in turn, and record the events from the DUT.
        """
        dut = self.context.get_active_dut()
        self.context.html("Running %s test for dut:%s" % (self.name, dut))
        test_item = self.context.create_db_test_item("%s Test" % self.name)
        gestures = self._create_grid(dut)

        self._initial_setup(dut)

        for index, gesture in enumerate(gestures):
            self.context.indicators.set_test_detail('Gesture', str(index + 1) + ' / ' + str(len(gestures)))

            self._pre_gesture_setup(gesture, dut)

            continuous_measurement = self.context.create_continuous_measurement(gesture)
            continuous_measurement.start(timeout=self.measurement_timeout, max_time=self.max_gesture_time)

            self._execute_gesture(gesture, dut)

            continuous_measurement.end()
            touch_list = continuous_measurement.parse_data()
            gesture_id = self._create_gesture(gesture, test_item)
            self._save_measurement_data(gesture_id, touch_list)

            self.context.breakpoint()

        self.context.close_db_test_item(test_item)

    def _initial_setup(self, dut):
        """
        Setup to be done one time before any gestures are executed.
        """
        pass

    @abstractmethod
    def _pre_gesture_setup(self, gesture, dut):
        """
        Setup to be done before each gesture is executed, including robot positioning.
        """
        pass

    @abstractmethod
    def _execute_gesture(self, gesture, dut):
        """
        Tell the robot to perform a single gesture.
        """
        pass

    def final_cleanup(self):
        """
        Clean up to be done one time after all gestures have been executed, or if the test is interrupted.
        """
        pass

    @abstractmethod
    def tip_is_valid(self):
        """
        Try to find the selected tips.
        :return: True if tips are found, False if not found
        """
        pass

    def pattern_is_valid(self):
        """
        Try to create the measurement grid to see if it is possible
        :return: True if the grid can be created, False if the grid cannot be created
        """
        dut = self.context.get_active_dut()
        try:
            _ = self._create_grid(dut)
            return True
        except GridCreationError as e:
            logger.error(str(e))
            return False

    @abstractmethod
    def _create_grid(self, dut):
        """
        Create grid of gesture shapes (lines, arcs, etc.) that define the geometry of the test case.
        :param dut: DUT where the grid is evaluated on.
        """
        pass

    def visualize_grid(self, dut):
        """
        Construct a visualization of the test case grid.
        :param dut: DUT where the grid is evaluated on.
        """
        test_pattern = self._create_grid(dut)
        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), test_pattern, dut.name)

    @abstractmethod
    def _create_gesture(self, gesture, test_item):
        """
        Create gesture and add to database.
        :return: id of created gesture.
        """
        pass

    def _save_measurement_data(self, gesture_id, touch_list):
        """
        Save measurements for a single gesture to database.
        """
        db_list = []
        self.context.clear_dut_points()

        for test_result in touch_list:
            results = self.results_class()

            results.panel_x = float(test_result.panel_x)
            results.panel_y = float(test_result.panel_y)
            results.pressure = float(test_result.pressure)
            results.finger_id = int(test_result.finger_id)
            results.time = test_result.time
            results.event = test_result.event
            results.gesture_id = gesture_id

            db_list.append(results)

            self.context.add_dut_point(float(test_result.panel_x), float(test_result.panel_y))

        self.context.db.add_all(db_list)

    def _get_finger_separation(self, clearance, tip1_size, tip2_size=None):
        """
        Given a desired finger clearance (edge to edge) and finger size, return the needed finger separation (center to
        center) if tips with given size were attached.
        :param clearance: Desired clearance between finger tips.
        :param tip1_size: Diameter of first tip (mm).
        :param tip2_size: Diameter of second tip (mm).  If None, assume the same as tip1.
        :return: The smallest finger separation (mm).
        """
        min_clearance = 0.1
        if clearance < min_clearance:
            raise ValueError("Finger clearance must be greater than {} mm.".format(min_clearance))

        if tip2_size is None:
            tip2_size = tip1_size
        separation = (tip1_size + tip2_size) / 2.0 + clearance

        # TODO (b/148627899): Poll the robot for minimum separation
        min_robot_separation = 10.5
        if separation < min_robot_separation:
            raise ValueError("Finger separation must be greater than {} mm.".format(min_robot_separation))

        return separation


def set_controls(tests, configurations):
    tests_with_set_controls = []

    for configuration in configurations:
        test = [test for test in tests if test.database_configuration == type(configuration)].pop()
        controlled_test = deepcopy(test)

        # Filter away the attributes that start with an underscore, because these are not controls we want to set
        configuration_dictionary = {key: value for key, value in configuration.__dict__.items() if
                                    not str(key).startswith('_')}

        for key, value in configuration_dictionary.items():
            if key == 'enabled':
                controlled_test.enabled = bool(value)
                continue

            if hasattr(controlled_test.controls, key):
                attr_type = type(getattr(controlled_test.controls, key))

                # Set control value. Cast value to the type that the value is initialized in test case init.
                controlled_test.controls.__setattr__(key, attr_type(value))
            else:
                raise AttributeError('No control with key "{}"'.format(key))

        tests_with_set_controls.append(controlled_test)

    return tests_with_set_controls


class NoiseTestStep(TestStep):
    """
    Abstract class for tests which use the function generator to inject noise.

    WARNING: All noise tests should only use one finger, and must be careful to leave the robot at azimuth 0 throughout
    test execution, because rotating the azimuth may cause damage while the function generator is attached.

    When creating noise tests, the robot should delay for one second with the finger touching the surface before
    performing the gesture. This is to allow the touch panel time to adapt to the noise. The first second of data
    should then be ignored in analysis.

    For all noise tests, the same gesture is performed repeatedly while a square wave of 10V is applied through the
    tip with frequencies between 0 and 500,000 Hz in increments of 500 Hz.
    """

    def __init__(self, name, context):
        super().__init__(name, context)

        self.noise_injection_needed = True

        sizes = list(map(str, sorted(context.tips_node.single_tips_by_size.keys())))

        self.controls.finger_size = sizes[0] if len(sizes) > 0 else ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.controls.freq_step = 500
        self.controls.info['freq_step'] = {'label': 'Noise frequency step (Hz)', 'min': 500}

        self.controls.device_path = 'COM2'
        self.controls.info['device_path'] = {'label': 'Function generator device path'}

        self.speed = 100.0
        self.generator = None
        self.test_gesture = None
        self.start_point = None

    def _initial_setup(self, dut):
        self.test_gesture = self._single_gesture_geometry(dut)
        if isinstance(self.test_gesture, Point):
            self.start_point = self.test_gesture
        elif isinstance(self.test_gesture, Line):
            self.start_point = Point(self.test_gesture.start_x, self.test_gesture.start_y, self.test_gesture.start_z)
        else:
            raise ValueError("Unsupported gesture type for Noise test")

        dut.move(self.start_point.x, self.start_point.y, dut.base_distance, azimuth=0)

        self.context.toggle_pause()
        self.context.ui.dialog_to_continue("Please attach the function generator to the robot tip, make sure DUT is "
                                           "grounded, and make sure the function generator is on.")
        self.context.breakpoint()

        self.generator = HP33120A(self.controls.device_path)

    def _pre_gesture_setup(self, frequency, dut):
        self.context.set_robot_default_speed()
        dut.move(self.start_point.x, self.start_point.y, dut.base_distance, azimuth=0)
        self.context.set_robot_speed(self.speed)

        self.generator.generate_function(HP33120A.Waveforms.SQUARE, frequency, 10)

    def final_cleanup(self):
        self.generator = None

    @abstractmethod
    def _single_gesture_geometry(self, dut):
        """
        Create the shape that defines the gesture that is performed at each frequency.
        """
        pass

    def _create_grid(self, dut):
        """
        For this test, all gestures performed by the robot are identical, but the frequency of noise supplied by the
        function generator differs.
        """
        frequencies = list(range(self.controls.freq_step, 500001, self.controls.freq_step))
        # Make the frequencies appear in the same order if using the same step. This will allow us to restart a test
        # run part-way through if there is a robot failure.
        random.seed(0)
        random.shuffle(frequencies)
        return frequencies

    def visualize_grid(self, dut):
        test_pattern = [self._single_gesture_geometry(dut)]
        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), test_pattern, dut.name)

    def tip_is_valid(self):
        try:
            self.context.tips_node.select_tips_by_size(float(self.controls.finger_size), 1, check_only=True)
            return True
        except TipSelectionError as e:
            logger.error(str(e))
            return False

    def pattern_is_valid(self):
        dut = self.context.get_active_dut()
        if len(self._create_grid(dut)) == 0:
            return False
        try:
            _ = self._single_gesture_geometry(dut)
            return True
        except GridCreationError as e:
            logger.error(str(e))
            return False


class ManualTestStep(TestStep):
    """
    Abstract class for tests where the operator is required to draw on the touch surface, with no robot gestures.
    """

    Gesture = namedtuple('Gesture', ['gesture', 'instruction_text_subs'])

    def __init__(self, name, context):
        super().__init__(name, context)
        self.is_manual = True

    @property
    @abstractmethod
    def _instruction_text(self):
        """
        Instruction text to be displayed for each gesture. Should allow text substitutions as provided by
        Gesture.instruction_text_subs, using the String format() function.
        """
        pass

    @abstractmethod
    def _create_grid(self):
        """
        Create list of ManualTestStep.Gesture tuples, which hold both:
         * the gesture shapes (lines, arcs, etc.) that define the geometry of the test case,
         * and a tuple holding text substitutions for the instruction text.
        """
        pass

    def _initial_setup(self, dut):
        dut.move(0.0, 0.0, 30.0, azimuth=0.0)

    def _pre_gesture_setup(self, gesture_tuple, dut):
        self.context.toggle_pause()
        self.context.ui.dialog_to_continue("Click Continue, and then: " +
                                           self._instruction_text.format(*gesture_tuple.instruction_text_subs))
        self.context.breakpoint()
        self._draw_target_gesture(gesture_tuple.gesture, dut)

    def _execute_gesture(self, gesture_tuple, dut):
        pass

    def visualize_grid(self, dut):
        test_pattern = [gesture_tuple.gesture for gesture_tuple in self._create_grid(dut)]
        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), test_pattern, dut.name)

    def _draw_target_gesture(self, gesture, dut):
        if isinstance(gesture, Line):
            self._draw_target_line(gesture, dut)
        else:
            raise ValueError("Unsupported gesture type for manual test")

    def _draw_target_line(self, line, dut):
        dut_node = self.context.get_active_dut_node()
        n_points = 100
        x_scale = dut_node.resolution[0] / (dut.width * n_points)
        y_scale = dut_node.resolution[1] / (dut.height * n_points)
        self.context.clear_dut_points()
        for i in range(n_points + 1):
            x = x_scale * (line.start_x * (n_points - i) + line.end_x * i)
            y = y_scale * (line.start_y * (n_points - i) + line.end_y * i)
            self.context.ui.add_dut_point(x, y)

    def tip_is_valid(self):
        return True

