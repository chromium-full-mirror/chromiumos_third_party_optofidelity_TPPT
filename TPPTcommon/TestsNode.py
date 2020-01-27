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
from TPPTcommon.Node import Node
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase, TestConfiguration, TestConfigurationGroup
import sys
import logging
from os import listdir
from os.path import isfile, join, splitext
from scriptpath import join_script_root_directory

logger = logging.getLogger(__name__)


class TestsNode(Node):
    """
    Node that hosts test cases as child nodes.
    Test cases can be imported from a directory of Python modules.
    """
    def __init__(self, name):
        super().__init__(name)

        self.test_case_modules = None

    def import_test_cases(self, context, subdirectory=None, exclude=None, config_db_init_success = False):
        """
        Import test cases from specific directory and make them child nodes for the sequence.
        """

        directory = join_script_root_directory('testcases')

        if subdirectory is not None:
            directory = join(directory, subdirectory)

        # Append test case folder to path to be able to import as Python modules.
        sys.path.append(directory)

        # Import all test cases located in directory as class names and add them to the sequence
        importfiles_ = [splitext(f)[0] for f in listdir(directory) if isfile(join(directory, f))]

        # Remove duplicates. This is O(n^2), but it doesn't matter since count of testcases won't ever be high.
        importfiles = []
        [importfiles.append(item) for item in importfiles_ if item not in importfiles]

        modules = []

        for class_name in importfiles:
            if exclude is not None and class_name in exclude:
                continue

            module = __import__(class_name, globals(), locals(), [class_name], 0)

            # Create instance of test step class and add as child node.
            Test = getattr(module, class_name)
            self.add_child(Test(context))

            modules.append(module)

        self.test_case_modules = modules

        # After importing the test classes, create the corresponding database tables
        # Done here to ensure that all the tables have been added to TestConfigBase.metadata
        if config_db_init_success:
            ConfigurationDatabase.TestConfigBase.metadata.create_all()


def save_test_configuration_to_database(configured_tests, configuration_name, configuration_group):
    try:
        session = ConfigurationDatabase.Session()
        for test in configured_tests:
            test.save_test_controls_to_database(session, configuration_name, configuration_group)

        session.commit()
    except Exception as e:
        session.rollback()
        logger.warning("Unable to save test parameters to database: " + str(e))
    finally:
        session.close()


def load_test_configuration_from_database(configured_tests, group_name, configuration_name):
    try:
        session = ConfigurationDatabase.Session()
        for test in configured_tests:
            set_test_controls_from_database(session, test, group_name, configuration_name)
    except Exception as e:
        logger.warning("Unable to load test parameters from database: " + str(e))
    finally:
        session.close()


def set_test_controls_from_database(session, node, group_name, configuration_name):
    try:
        if node.database_configuration:
            group_id = session.query(TestConfigurationGroup).filter(TestConfigurationGroup.name == group_name).one_or_none().id

            test_configuration_id_query = session.query(TestConfiguration.id) \
                                                 .filter(TestConfiguration.name == configuration_name) \
                                                 .filter(TestConfiguration.configuration_group == group_id).one_or_none()


            test_configuration_id = test_configuration_id_query.id if test_configuration_id_query is not None else None

            config = session.query(node.database_configuration) \
                            .filter(node.database_configuration._test_configuration == test_configuration_id) \
                            .one_or_none()

            if config is None:
                raise Exception('No configuration found for test {} with name {}'.format(str(node), configuration_name))

            controls = node.controls.get_controls()
            for control in controls:
                try:
                    # Set the current value for the control based on the queried configuration,
                    # or use the default value if for some reason the attribute is missing in the configuration
                    control_type = type(getattr(node.controls, control))
                    node.controls.__setattr__(control, control_type(config.__getattribute__(control)))
                except AttributeError:
                    pass

            node.enabled = bool(config.enabled)
    # If test node in question doesn't have database_configuration class defined, use defaults
    except AttributeError:
        pass
