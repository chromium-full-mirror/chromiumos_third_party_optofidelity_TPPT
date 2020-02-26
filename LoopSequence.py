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
import os

import TPPTcommon.Drivers.devicesocket as devicesocket
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
import TPPTcommon.Drivers.adb as adb
from TPPTcommon.Drivers.pitwrapper import PITWrapper
from TPPTcommon.grid import GridVisualizer
from TPPTcommon.Measurement.DeviceSocket import *
from TPPTcommon.Measurement.PIT import *
from TPPTcommon.Measurement.Dummy import *
from TPPTcommon.Measurement.Adb import *
from TPPTcommon.DutNode import DutsNode
from TPPTcommon.TipNode import TipsNode
from TPPTcommon.TestsNode import TestsNode, load_test_configuration_from_database, save_test_configuration_to_database
from TPPTcommon.TestStep import set_controls
from TPPTcommon.SettingsNode import SettingsNode
from TPPTcommon.Node import Parameter, RootNode, Stop, save_script_values, \
    load_script_values, load_script_history_headers
from TPPTcommon.Indicators import Indicators
import MeasurementDB
from scriptpath import join_script_root_directory
from client.tntclient.tnt_client import TnTClient
import threading
import traceback

logger = logging.getLogger(__name__)

# TnT Server address and port.
SERVER_HOST = '127.0.0.1'
SERVER_PORT = '8000'

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Absolute path of database file where results are saved.
DATABASE_PATH = join_script_root_directory('database.sqlite')

# Absolute path of file where script parameter history is saved.
HISTORY_PATH = join_script_root_directory('history.json')

# State of script context
STATE_WAITING = 0
STATE_EXECUTING = 1
STATE_PAUSED = 2
STATE_STOPPED = 3


class Context:
    """
    Contains data that is used by test cases such as
    - TnT client
    - Sequence nodes
    - Measurement data collection drivers
    - Interface to UI
    """

    def __init__(self, ui):
        """
        This is called when script is loaded.
        Sets up TnT client, discovers available DUTs and tips, creates GUI controls for test cases,
        initializes TCP socket and loads test cases as child nodes.
        :param ui: User interface object that initializes script context.
        """

        self.ui = ui

        self.config_db_init_success = False
        try:
            if ConfigurationDatabase.initialize_configuration_database():
                self.config_db_init_success = True
                logger.info('Configuration database initialization successful')
        except Exception as e:
            logger.error('Failed to initialize configuration database: ' + str(e))

        self.state = STATE_WAITING

        # Test sequence is executed in a thread to keep the calling thread responsive.
        self.execution_thread = None
        self.active_group = ''

        # This is used to determine whether to run configuration group tests or the test from the UI
        self.run_configuration_group = False

        # Parameters show up in UI as text input fields.
        self.parameters = []
        self.parameters.append(Parameter('Program'))
        self.parameters.append(Parameter('Manufacturer'))
        self.parameters.append(Parameter('Version'))
        self.parameters.append(Parameter('Operator'))
        self.parameters.append(Parameter('Station ID'))
        self.parameters.append(Parameter('Serial'))
        self.parameters.append(Parameter('Notes', single_line=False))

        self.indicators = Indicators(ui)

        # These are tuples of type (function, label). UI creates buttons for each tuple.
        self.callables = [(self.visualize_grids, 'Show measurement points')]

        # Connect to TnT Server by using TnTClient and get the default robot.
        self.tnt = TnTClient(SERVER_HOST, SERVER_PORT)
        self.robot = self.tnt.robot("Robot1")

        # DUT ID is used to track DUT database entry during test session.
        self.dut_id = None

        self.test_session = None
        self.test_session_id = None

        # Create and start TCP socket where DUTs can connect and send touch events.
        self.dsock = devicesocket.DeviceSocket()
        self.html('Started TCP Socket.')

        self.adb = adb.Adb()
        self.dummy_logging = Dummy_logging()

        # PIT is initialized when required.
        self.pit = None
        self.pit_connected = False

        # Root node contains all other nodes.
        self.root_node = RootNode()

        self.settings_node = SettingsNode()
        self.root_node.add_child(self.settings_node)

        self.duts_node = DutsNode(self)
        self.duts_node.create_duts()
        self.root_node.add_child(self.duts_node)

        self.tips_node = TipsNode(self)
        self.tips_node.create_tips()

        # Hide tips node from UI as test cases control tips.
        #self.root_node.add_child(self.tips_node)

        self.tests_node = TestsNode('Tests')

        # Remove exclude parameter to make burning test visible in UI.
        self.tests_node.import_test_cases(self, exclude=["BurningTest"],
                                          config_db_init_success = self.config_db_init_success)

        self.root_node.add_child(self.tests_node)

        self.db = None

        # Update initial values in UI.
        ui.set_history_headers(self.load_history_headers())
        ui.set_script_nodes(self.root_node.to_dict())
        ui.set_script_parameters(self.parameters_to_list())
        if self.config_db_init_success:
            ui.set_configuration_group_headers(ConfigurationDatabase.load_configuration_group_names())

        ui.set_script_callables([c[1] for c in self.callables])

        ui.script_ready(self.config_db_init_success)

    def get_parameter(self, name):
        """
        Get parameter by name.
        :param name: Name of parameter
        :return: The parameter
        """
        for p in self.parameters:
            if p.name == name:
                return p

    def get_tppt_version(self):
        """
        Returns TPPT version number string including Jenkins build number from version.txt.
        If version.txt doesn't exist, version number is set to "x.x".
        :return Version number
        """

        version_number = "x"
        build_number = "x"

        # Read build number from version.txt
        path = os.path.dirname(os.path.abspath(__file__))
        version_file_name = os.path.join(path, "version.txt")
        if os.path.exists(version_file_name):
            with open(version_file_name, 'r') as file:
                # Read all "key: value" pairs into a dict
                version_info = dict(line.split(':', 1) for line in file)
                if 'Version' in version_info:
                    version_number = version_info['Version'].strip()
                if 'Build' in version_info:
                    build_number = version_info['Build'].strip()

        return version_number + "." + build_number

    def create_dut_visualization(self, xpixels, ypixels):
        """
        Create DUT visualization in UI to show test step progress.
        :param xpixels: Number of DUT screen pixels in x-direction.
        :param ypixels: Number of DUT screen pixels in y-direction.
        """
        self.ui.create_dut_svg(xpixels, ypixels)

    def add_dut_point(self, x, y):
        """
        Add DUT measurement point to UI to show test step progress.
        :param x: X-coordinate of point in pixels.
        :param y: Y-coordinate of point in pixels.
        """
        self.ui.add_dut_point(x, y)

    def clear_dut_points(self):
        """
        Clear DUT measurement points in UI.
        """
        self.ui.clear_dut_points()

    def execute_burning_test(self, burning_test):
        """
        Execute burning test. Only Burning test is executed even though more test cases
        would have been selected.
        """
        # Make sure there is no tip in the separated finger.
        #self.robot.detach_tip(1)

        # Set default robot speed before running test case. Previous test may have changed current robot speed.
        self.set_robot_default_speed()

        self.clear_dut_points()

        self.indicators.set_status("Executing test case " + burning_test.name)

        # Run test case.
        burning_test.execute()

    def execute_configured_tests(self):
        """
        Execute test cases that are fully configured by their control values.
        This means that e.g. tip changes are done within test case.
        """
        if not self.run_configuration_group and self.tests_node.num_enabled_children == 0:
            return

        # Create list of the test that are go
        executable_tests = self.create_executable_test_list()

        # Check that all tests are valid
        if not self.is_valid(executable_tests):
            return

        test_count = 0

        self.breakpoint()

        for test in executable_tests:
            self.select_tips(test)

            # Jump over DUT without specific jump height to avoid problems in case tip was changed.
            active_dut = self.get_active_dut()
            active_dut.jump(0.0, 0.0, active_dut.base_distance)

            # Set default robot speed before running test case. Previous test may have changed current robot speed.
            self.set_robot_default_speed()

            self.clear_dut_points()

            test_count += 1
            self.indicators.set_status("Executing test case " + test.name + ' (' + str(test_count) + ' / ' + str(
                len(executable_tests)) + ')')

            # Run test case.
            test.execute()

    def select_tips_by_name(self, test):
        """
        Select tips for the test. Test object must have the "finger_name" control, Second finger is
        selected with the "finger2_name" control.
        :param test: Active test object
        """
        self.tips_node.set_active_tip_by_name(test.controls.finger_name)
        if hasattr(test.controls, "finger2_name") and len(test.controls.finger2_name) > 0:
            self.robot.change_tip(test.controls.finger2_name, 1)
        else:
            self.robot.detach_tip(1)

    def select_tips(self, test):
        """
        Select tips for the test. Test object must either have the "finger_name" control,
        or the "finger_size" control. Second finger is selected with the "finger2_name" control
        or the "num_fingers" control.
        If the object doesn't have those parameters, no exception is raised and the test is allowed
        to select its own tips.
        :param test: Active test object
        """
        if hasattr(test.controls, "finger_name") and len(test.controls.finger_name) > 0:
            self.select_tips_by_name(test)
        elif hasattr(test.controls, "finger_size"):
            num_fingers = getattr(test.controls, "num_fingers", 1)
            self.tips_node.select_tips_by_size(test.controls.finger_size, num_fingers)

    def is_valid(self, tests):
        """
        Check that all the test grid patterns are executable and tips are found. Always inspects all
        the tests so that user gets the information of all failing tests in the same time.
        :param tests: test objects to be checked
        :return: True if all tests are valid, False if some of the tests are not valid
        """
        tests_valid = True
        active_dut = self.get_active_dut().name
        self.html('Checking test pattern and tip validity for all the tests for {}'.format(active_dut))

        for test in tests:
            # Going through all the tests that are going to be run
            if not test.tip_is_valid():
                tip_error_str = 'Valid tips not found for {test_name} test'.format(test_name=test.name)
                self.html_error(tip_error_str)
                tests_valid = False
            if not test.pattern_is_valid():
                # The test controls of the failing test need to be told to the user
                controls_dict = test.controls.get_control_dictionary()
                pattern_error_str = 'Invalid test pattern found in {test_name} test \n'.format(test_name=test.name)
                self.html_error(pattern_error_str)
                for key, value in controls_dict.items():
                    pattern_error_str += '{key}: {value} \n'.format(key=key, value=value)
                message = 'More details about the failing pattern: \n' + pattern_error_str
                logger.error(message)
                tests_valid = False

        if not tests_valid:
            self.html_error('All the tests are not valid for {}. '
                            'Stopping tests for the DUT. See log for details'.format(active_dut))
        else:
            self.html('All test patterns are valid and tips are found')

        return tests_valid

    def create_executable_test_list(self):
        """
        | Creates a test list to run from the configuration group if the call came from run group.
        | Otherwise run the tests enabled in the UI configuration tree.

        :return: List of tests to be executed
        """
        if not self.run_configuration_group:
            configured_tests = self.tests_node.get_enabled_children()
        else:
            configured_tests_configuration_classes = [child.database_configuration for child in
                                                      self.tests_node.children]

            test_configurations = \
                ConfigurationDatabase.load_configurations_by_group_name(self.active_group,
                                                                        configured_tests_configuration_classes)

            configured_tests = set_controls(self.tests_node.children, test_configurations)
            configured_tests.sort(
                key=lambda test: [getattr(test.controls, control, "") for control in
                                  ["ground_status", "noise_status",
                                   "finger_name", "finger2_name", "finger_size", "num_fingers",
                                   "display_background"]])

        return configured_tests

    def _execute(self):
        """
        This is called when test is started.
        Loops every DUT and tip and calls test case child nodes.
        TODO: Should perhaps refactor looping DUTs and tips into separate nodes for flexibility.
        """

        # Reset indicators.
        self.indicators = Indicators(self.ui)
        self.indicators.update_ui()

        self.html_color("Starting test sequence (" + time.strftime(TIME_FORMAT) + ")", "green")

        if not self.duts_node.check_duts():
            return

        # Make the axial finger active as test cases are designed for that.
        self.robot.set_active_finger(0)

        # Create test session database entry.
        self.test_session = MeasurementDB.TestSession()
        self.test_session.operator = self.get_parameter('Operator').value
        self.test_session.starttime = time.strftime(TIME_FORMAT)
        self.test_session.notes = self.get_parameter('Notes').value
        self.test_session.tnt_version = self.tnt.version()
        self.test_session.tppt_version = self.get_tppt_version()
        self.test_session.station_id = self.get_parameter('Station ID').value

        self.test_session_id = self.db.add(self.test_session)

        # if Burning Test is selected, only it will be executed
        for test in self.tests_node.children:
            if test.enabled and test.name == "Burning test":
                self.execute_burning_test(test)
                return
            else:
                break

        dut_count = 0

        # Loop through enabled DUTs.
        for dut_node in self.duts_node.children:
            if not dut_node.enabled:
                continue

            # At the moment this is not very useful as jump between DUTs is done in test case execution.
            self.indicators.set_status("Changing DUT to " + dut_node.name)

            dut = dut_node.tnt_dut


            # Try to fetch device resolution automatically if enabled in DUT settings.
            # Does not work with Dummy driver
            if dut_node.controls.fetch_resolution:
                try:
                    dut_info = dut.info()
                    display_width = int(dut_info['display_resolution']['width'])
                    display_height = int(dut_info['display_resolution']['height'])
                    # Saving the resolution to dut node
                    dut_node.controls.dut_resolution = [display_width, display_height]
                    self.html('Fetching resolution successful: '
                              'screen width: ' + str(display_width) +
                              'p, screen height: ' + str(display_height) + 'p')
                except:
                    self.html_color('Fetching resolution automatically failed. Stopping script execution', color = 'red')
                    continue

            # It is important we don't set dut_node active before since this
            # updates resolution value from controls to actual usage
            self.duts_node.set_active_dut(dut_node)

            # If we are using Adb driver we set the parameters here
            if self.get_active_dut_driver() == "Adb":
                display_width = dut_node.controls.dut_resolution[0]
                display_height = dut_node.controls.dut_resolution[1]
                adb_event = dut_node.controls.adb_event_id
                if not self.adb.initialize_settings(display_width, display_height, adb_event):
                    self.html_color('Adb initialization failed, see log for details', 'red')
                    continue

            dut_count += 1
            self.indicators.set_dut_name(dut_node.name + ' (' + str(dut_count) + ' / ' + str(self.duts_node.num_enabled_children) + ')')

            # Assign DUT db table ID to be used by test cases to create test case database entries.
            self.dut_id = self.create_dut_db_entry(dut)

            self.save_control_values()

            # Jump over DUT origin.
            self.set_robot_dut_change_speed()
            active_dut = self.get_active_dut()
            active_dut.jump(0.0, 0.0, active_dut.base_distance)

            # Configured tests.
            self.execute_configured_tests()
            # Update test session status.
            self.test_session.endtime = time.strftime(TIME_FORMAT)
            self.test_session.invalid = False
            self.db.update(self.test_session)

        self.html_color('Test sequence completed', 'green')
        self.indicators.set_status("Test sequence completed")

    def _try_execute(self):
        """
        Execute test cases in try block to catch stop condition.
        """

        # Open database just before execution to make sure that SQL objects are created in the same thread.
        self.db = MeasurementDB.ResultDatabase(DATABASE_PATH, self.tests_node.test_case_modules)

        try:
            self._execute()
        except Stop:  # User stopped execution
            pass
        except Exception as e:
            # Call UI error function directly as exception is not passed to calling thread.
            message = str(e)
            message += traceback.format_exc()
            self.ui.script_failed(message)

        self.state = STATE_WAITING
        self.ui.script_finished()

    def save_control_values(self):
        """
        Save values of controls to database in order to restore them later if needed.
        """

        dut_node = self.duts_node.active_dut_node

        # Save all control values to session parameters table in database
        for control in dut_node.controls.get_controls():
            parameter_label = dut_node.controls.info[control]["label"]

            session_parameters = MeasurementDB.DutParameters()
            session_parameters.dut_id = self.dut_id

            # TODO: Might be better to use control key as parameter name instead of label.
            session_parameters.name = parameter_label

            selected_value = getattr(dut_node.controls, control)

            # Database expects to receive some values in float;float or int;int format
            if control == 'dut_resolution' or control == 'offset':
                selected_value = str(selected_value[0]) + ";" + str(selected_value[1])

            if isinstance(selected_value, bool):
                session_parameters.valueString = str(int(selected_value))
            else:
                session_parameters.valueString = str(selected_value)

            self.db.add(session_parameters)

    def create_dut_db_entry(self, dut):
        """
        Create database entry from DUT data.
        :param dut: DUT to use.
        :return: ID of DUT database table entry.
        """

        # Each test run creates new DUT information in case DUT parameters were changed.
        test_dut = MeasurementDB.TestDUT()
        test_dut.program = self.get_parameter('Program').value
        test_dut.manufacturer = self.get_parameter('Manufacturer').value
        test_dut.batch = self.get_parameter('Version').value
        test_dut.serial = self.get_parameter('Serial').value
        test_dut.sample_id = str(dut)
        if len(dut.svg_data()) > 0:
            test_dut.svg_data = dut.svg_data().encode()
        else:
            test_dut.svg_data = None

        self.db.add(test_dut)


        # Add DUT dimensions
        session_parameters = MeasurementDB.DutParameters()
        session_parameters.dut_id = test_dut.id
        session_parameters.name = 'DUT dimensions [x;y, mm]'
        session_parameters.valueString = "%s;%s" % (self.tnt.dut(str(dut)).width,
                                                    self.tnt.dut(str(dut)).height)

        self.db.add(session_parameters)

        return test_dut.id

    def initialize_pit(self):
        """
        Initialize PIT for getting touch events.
        """
        if self.duts_node.active_driver == "PIT-USB":
            dutHandlerName = "PIT_USB"
            dutHandlerIP = '10.10.14.2'
        else:
            dutHandlerName = "PIT"
            dutHandlerIP = '10.10.10.2'

        if not self.pit_connected:
            self.html("Accessing " + dutHandlerName + "...")
            self.pit = PITWrapper(host=dutHandlerIP, port=8080)
            self.pit_connected = True

        pit_drivers_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "TPPTcommon", "PIT_Drivers")

        driver = open(os.path.join(pit_drivers_path, (
            self.duts_node.active_dut_node.pit_driver))).read()
        self.pit.LoadDriver(driver)

        # Select PIT slot
        self.pit.Multiplexer(self.duts_node.active_dut_node.pit_index)

        # Initialize current DUT
        self.html("Initializing " + dutHandlerName + " driver")

        try:
            self.pit.InitializePanel()
        except:
            self.html(dutHandlerName + " driver initialization failed")

    def visualize_grids(self):
        """
        Visualizes the test grids.
        """
        try:
            self.ui.change_to_figure_page()
            tests = []

            for test in self.tests_node.children:
                if test.enabled:
                    tests.append(test)

            if not self.duts_node.check_duts():
                self.html_color('Could not display test grid:', 'red')
                self.html_color('No DUTS selected.', 'red')
                return

            if not tests:
                self.html_color('Could not display test grid:', 'red')
                self.html_color('No tests selected.', 'red')
                #self.app.warning_dialog(self, "No tests selected.", caption = "Could not display test grid!")
                self.ui.hide_loading_element()
                return

            grids = {}
            for i in tests:
                i_name = i.__class__.__name__
                for j in self.duts_node.children:
                    if not j.enabled:
                        continue

                    if i_name not in grids: grids[i_name] = []

                    if hasattr(i, 'visualize_grid'):
                        grids[i_name].append(i.visualize_grid(j.tnt_dut))

            plotter = GridVisualizer()
            plotter.AddGridList(grids)
            images = plotter.Render()
            self.ui.hide_loading_element()
            self.ui.append_images_to_figure_page(images)
        except Exception as e:
            self.html("visualize_grids: %s" % e)
            self.ui.script_failed(str(e))
            #self.dialog("Active grid calculation failed!\n It seems that the grid value is too big.\nPlease try again with different grid value (e.g. 2.0)")

    def get_active_dut(self):
        """
        :return: The active DUT.
        """
        if self.duts_node.active_dut is None:
            self.html("Could not find active DUT")
            raise Exception("Could not find active DUT")

        return self.duts_node.active_dut

    def get_active_dut_node(self):
        """
        :return: The active DUT's node.
        """
        dut = self.duts_node.active_dut_node
        if dut is None:
            self.html("Could not find active DUT node")
            raise Exception("Could not find active DUT node")
        return dut

    def get_active_tip(self):
        """
        :return: The active tip.
        """
        if self.tips_node.active_tip is None:
            self.html("Could not find active tip")
            raise Exception("Could not find active tip")

        return self.tips_node.active_tip

    def get_pit_dut_index(self):
        """
        Get current DUT index for PIT. This is PIT slot - 1.
        :return: The PIT index.
        """
        return self.duts_node.active_dut_node.pit_index

    def get_active_dut_driver(self):
        """
        :return: Current DUT driver.
        """
        return self.duts_node.active_driver

    def create_db_test_item(self, test_name):
        """
        Creates new test to test table to database.
        :param test_name: Name of test that is used to find the test type ID for database.
        :return: TestItem object.
        """

        # Create dictionary to find test type ID by test name.
        test_types = self.db.get_TestTypes()
        logger.debug(test_types)
        test_dictionary = {}
        for test_type in test_types:
            test_dictionary[test_type.name] = test_type.id

        # Create a new ddt test table to database
        ddt_test = MeasurementDB.TestItem()
        ddt_test.dut_id = self.dut_id
        ddt_test.finger_type = str(self.get_active_tip()) if self.tips_node.active_tip is not None else ""
        ddt_test.testsession_id = self.test_session_id
        ddt_test.slot_id = int(self.duts_node.active_dut_node.pit_index) + 1
        ddt_test.starttime = time.strftime(TIME_FORMAT)
        ddt_test.invalid = True
        ddt_test.testtype_id = test_dictionary[test_name]

        # Add and commit but don't expire.
        # This is because close_db_test_item() later changes test status (e.g. invalid to False).
        self.db.add(ddt_test, expire_on_commit=False)

        return ddt_test

    def close_db_test_item(self, db_item, kmsg_log = None):
        """
        Close database test item i.e. commit changes to database.
        This also marks the test item complete for the analyzer.
        :param db_item: Database item to close. Must have been created with create_db_test_item().
        :param kmsg_log: android log that is read through adb-connection and should be saved
        always for one test
        """
        db_item.endtime = time.strftime(TIME_FORMAT)
        db_item.invalid = False

        if kmsg_log is not None:
            db_item.kmsg_log = kmsg_log

        self.db.update(db_item)
        self.html_color("Test step completed", "green")

    def set_robot_speed(self, speed, acceleration=None):
        self.robot.set_speed(speed, acceleration)

    def get_travel_time(self, distance):
        """
        Get the time it takes for robot to move given distance according to current speed and acceleration.
        :param distance: Distance in millimeters.
        :return: Time in seconds.
        """

        data = self.robot.get_speed()
        robot_speed = data["speed"]
        robot_acceleration = data["acceleration"]

        if robot_acceleration == 0:
            return distance / robot_speed
        else:
            return (math.sqrt(
                robot_speed ** 2 + 2 * distance * robot_acceleration) - robot_speed) / robot_acceleration

    def set_robot_default_speed(self):
        """
        Set speed and acceleration defined by main sequence controls.
        """
        self.set_robot_speed(self.settings_node.controls.default_speed, self.settings_node.controls.default_acceleration)
        

    def set_robot_dut_change_speed(self):
        """
        Set speed and acceleration that are appropriate for changing DUTs.
        Usually should use high speed but medium acceleration.
        """

        self.set_robot_speed(250, 100)

    def send_image(self, image_filename=None):
        """
        Sends given image to DUT. JPG and PNG image formats are supported.
        :param image_filename: Image filename.
        :return: Nothing.
        """

        # In case there is some error in sending image, retry a fixed number of times.
        num_retrys = 5

        for i in range(0, num_retrys):
            try:
                if image_filename is not None and len(image_filename) > 0:
                    script_file_path = os.path.dirname(os.path.realpath(__file__))
                    image_filename = os.path.join(script_file_path, 'background_images', image_filename)
                else:
                    image_filename = None
                dut = self.get_active_dut()

                if image_filename is not None:
                    with open(image_filename, "rb") as file:
                        im_data = file.read()
                else:
                    im_data = None

                dut.show_image(im_data)
                return
            except Exception as e:  # Not sure what kind of errors may occur but retry in case of any error.
                message = "Sending image to DUT failed. Retrying ({}/{}) ...".format(i + 1, num_retrys)
                self.html_error(message)

                # Sleep for a while between retries in case e.g. network has some temporary problem.
                time.sleep(1.0)

        # If problem is not fixed by retrying, raise exception to be handled by caller.
        raise Exception("Sending image to DUT failed after retries.")


    def start_log(self):
        handler = self.duts_node.active_driver
        if handler == "Dummy":
            self.dummy_logging.start_log()
        else:
            self.adb.start_log()


    def stop_log(self):
        handler = self.duts_node.active_driver
        if handler == "Dummy":
            return self.dummy_logging.stop_log()
        else:
            return self.adb.stop_log()

    def create_tap_measurement(self, point):
        '''
        Create tap measurement instance according to current state (DUT, tip).
        :param point: Robot point where tap is performed.
        :return: Tap measurement object based on TapMeasurement super class.
        '''

        handler = self.duts_node.active_driver

        if handler == "PIT":
            return TapMeasurementPIT(self.indicators, point, self.pit, self.duts_node.active_dut_node.pit_index)
        elif handler == "Dummy":
            return TapMeasurementDummy(self.indicators, point)
        elif handler == "Adb":
            return TapMeasurementAdb(self.indicators, point, self.adb)
        else:  # "TCP socket"
            return TapMeasurementDeviceSocket(self.indicators, point, self.dsock)

    def create_continuous_measurement(self, line):
        '''
        Create continuous measurement instance according to current state (DUT, tip).
        :param line: Line that robot will swipe.
        :return: Continuous measurement object based on ContinuousMeasurement super class.
        '''

        handler = self.duts_node.active_driver

        if handler == "PIT":
            return ContinuousMeasurementPIT(self.indicators, line, self.pit)
        elif handler == "Dummy":
            active_dut_node = self.get_active_dut_node()
            return ContinuousMeasurementDummy(self.indicators, line, active_dut_node)
        elif handler == "Adb":
            return ContinuousMeasurementAdb(self.indicators, line, self.adb)
        else:  # "TCP socket"
            return ContinuousMeasurementDeviceSocket(self.indicators, line, self.dsock)

    def set_indicators(self, text):
        """
        Set indicators in UI.
        Indicators is currently just a text caption that can use HTML / CSS.
        :param text: Text to set for indicator.
        """
        self.ui.set_indicators(text)

    def stop(self):
        """
        Stop test execution.
        Assuming that execute_tests() is running in another thread, the execution there will stop.
        """
        if self.state != STATE_WAITING:
            self.state = STATE_STOPPED

        self.execution_thread.join()

    def toggle_pause(self):
        """
        Stop or continue test execution.
        """
        if self.state == STATE_EXECUTING:
            self.state = STATE_PAUSED
        elif self.state == STATE_PAUSED:
            self.state = STATE_EXECUTING

    def breakpoint(self):
        """
        Test whether test execution should pause or stop.
        This should be called by test cases at regular intervals.
        """
        while self.state == STATE_PAUSED:
            time.sleep(1.0)

        if self.state == STATE_STOPPED:
            raise Stop()

    def html(self, message):
        """
        Print message to UI and log.
        Can use HTML / CSS.
        :param message: Message to print.
        """
        self.ui.log(message)
        logger.info(message)

    def html_color(self, text, color):
        """
        Print message to UI and log.
        Can use HTML / CSS.
        :param message: Message to print.
        :param color: Color of the message. A string such as 'red'.
        """
        self.ui.log('<font color="%s">%s</font>' %(color, text))
        logger.info(text)

    def html_error(self, error_message):
        """
        Print error message to UI (with red color) and log.
        Can use HTML/CSS
        :param error_message: Message to print
        :return: -
        """
        self.ui.log('<font color="red">%s</font>' % (error_message))
        logger.error(error_message)

    def execute_tests(self, run_configuration_group=False):
        """
        Executes test cases.
        This is called by UI.
        Launches a separate thread for test case execution to keep the calling UI responsive.
        UI should call stop() even after completion of test sequence to join the thread.
        """

        if self.state != STATE_WAITING:
            return

        self.state = STATE_EXECUTING
        self.run_configuration_group = run_configuration_group

        #self.root.traverse('execute', self)

        self.execution_thread = threading.Thread(target=self._try_execute)
        self.execution_thread.start()

    def save(self):
        """
        Save script value state to history file.
        """
        save_script_values(HISTORY_PATH, self.root_node.children, self.parameters)

    def save_configuration_as(self, configuration_name, configuration_group):
        """
        Save script value state to the database
        """
        save_test_configuration_to_database(self.tests_node.children, configuration_name, configuration_group)

    def load(self, name, file_path=HISTORY_PATH):
        """
        Load script value state from history file.
        :param name: Name of the piece of history to load (date and time of save).
        """
        load_script_values(file_path, name, self.root_node.children, self.parameters)

        # Update script content in UI according to loaded values.
        self.ui.set_script_nodes(self.root_node.to_dict())
        self.ui.set_script_parameters(self.parameters_to_list())
        self.ui.set_script_callables([c[1] for c in self.callables])

    def load_configuration(self, group_name ='', configuration_name=''):
        """
        Load script value state from the database with the given name
        :param configuration_name: Unique name that identifies the wanted configuration
        """
        load_test_configuration_from_database(self.tests_node.children, group_name, configuration_name)
        self.ui.set_script_nodes(self.root_node.to_dict())

    def create_new_configuration_group(self, group_name):
        """
        This is called by UI. Allows creating new configuration groups from the UI.
        """
        ConfigurationDatabase.create_new_configuration_group(group_name)
        self.update_configuration_group_headers(group_name)
        self.update_configuration_headers_for_group(group_name)

    def delete_configuration_group(self, group_name):
        """
        This is called by UI. Allows deleting of current configuration group from the UI.
        """
        ConfigurationDatabase.delete_configuration_group(group_name)
        self.update_configuration_group_headers('')
        self.update_configuration_headers_for_group('')

    def delete_configuration(self, configuration_name):
        """
        This is called by UI. Allows deleting of current configuration from the UI.
        """
        ConfigurationDatabase.delete_configuration(configuration_name)

    def duplicate_active_configuration_group(self, active_group_name, new_group_name):
        """
        This is called by UI. Duplicates the current configuration group and related configurations
        :param active_group_name: The currently active configuration group that is copied
        :param new_group_name: Name for the duplicate group (names are an unique identifier)
        """
        ConfigurationDatabase.duplicate_configuration_group(active_group_name, new_group_name)
        self.update_configuration_group_headers(new_group_name)
        self.update_configuration_headers_for_group(new_group_name)

    def update_configuration_group_headers(self, select_value=None):
        """
        Updates the configuration group dropdown on the UI with the current data.
        Called after initialization, and when creating or deleting groups.
        :param select_value: Value to select from header list. None to keep current selection.
        """
        self.ui.set_configuration_group_headers(ConfigurationDatabase.load_configuration_group_names(), select_value)

    def update_configuration_headers_for_group(self, group_name):
        """
        Updates the configuration dropdown on the UI with the current data.
        Called after initialization, and when creating or deleting configurations.
        """
        self.active_group = group_name
        self.ui.set_configuration_headers(ConfigurationDatabase.load_configuration_names_for_group(group_name))

    def load_history_headers(self):
        """
        Load script value state history headers i.e. dates and times.
        :return: List of header strings.
        """
        return load_script_history_headers(HISTORY_PATH)

    def parameters_to_list(self):
        """
        Get parameters as list of dictionary objects.
        :return: Parameter list.
        """
        return [p.to_dict() for p in self.parameters]

    def execute_callable(self, callable_name):
        """
        Execute callable by name.
        :param callable_name: Name of callable.
        """

        for c in self.callables:
            if c[1] == callable_name:
                c[0]()
                break

    def update_nodes(self, root_node):
        """
        Update node hierarchy according to given dictionary hierarchy.
        :param root_node: Dictionary of root node that has updated values.
        """
        self.root_node.from_dict(root_node)

    def set_parameter(self, name, value):
        """
        Set script parameter.
        :param name: Name of parameter to set.
        :param value: Value string to set to paramter.
        """
        self.get_parameter(name).value = value

    def get_test_nodes(self):
        test_nodes = []

        for child in self.root_node.children:
            # Find the 'Tests' root node
            if isinstance(child, TestsNode):
                # The child.children is list of TestsNodes that group finger type tests together
                for grandchild in child.children:
                    # grandchild.children is a list of individual TestNodes
                    test_nodes = test_nodes + grandchild.children

        return test_nodes


class UiProxyMultiprocess:
    """
    Proxy class for UI object that is used in multiprocess scheme.
    In this scheme script runs in separate Python process and calls to UI are
    done via Pipe connection object.

    From script's point of view, calling UI via this proxy object has the
    the effect as calling the UI object methods directly in singleprocess scheme.
    """

    def __init__(self, conn):
        self.conn = conn

    def _call_ui(self, method_name, *args):
        self.conn.send((method_name, args))

    def __getattr__(self, name):
        """
        Override attribute getter to redirect UI method calls via Pipe connection.
        :param name: Name of UI method to call.
        :return: Function object that is proxy for the UI method.
        """
        return lambda *args: self._call_ui(name, *args)


class PipeLogHandler(logging.Handler):
    """
    Log handler that passes log record to UI process to be shown in application console.
    """
    def __init__(self, ui):
        logging.Handler.__init__(self)
        self.ui = ui

    def emit(self, record):
        try:
            self.ui.sys_log(record)
        except:
            self.handleError(record)


def run_multiprocess(conn):
    """
    In multiprocess scheme, UI calls this function after launching Python process for the script.
    The script Python process then creates Context object and interacts with UI via Pipe connection.
    This is in contrast to singleprocess scheme, where UI directly imports this Python module and
    creates Context object in the UI process.
    :param conn: Pipe connection object provided by UI for scripts to interact with the UI.
    """

    # Create UI proxy that script uses to communicate to UI.
    ui = UiProxyMultiprocess(conn)

    # Add log handler to pass script logs to UI process.
    root = logging.getLogger()
    root.addHandler(PipeLogHandler(ui))

    # Change level to affect which messages are shown in UI console.
    root.setLevel(logging.DEBUG)

    # Create script context.
    context = Context(ui)

    # Receive messages from UI via Pipe connection and execute corresponding context methods.
    while True:
        msg = conn.recv()

        method_name = msg[0]
        args = msg[1]

        # 'exit' is special message and signals that script process should terminate.
        if method_name == 'exit':
            ui.exit()
            break

        method = getattr(context, method_name)
        method(*args)
