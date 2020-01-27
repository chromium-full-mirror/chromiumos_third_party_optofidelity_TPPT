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
import decimal
from copy import copy, deepcopy
from TPPTcommon.Node import Node
from TPPTcommon.ConfigurationDatabase import TestConfiguration, ConfigurationDatabase, TestConfigurationGroup


class TestStep(Node):
    def __init__(self, name):
        super().__init__(name)
        self.display_enabled = True
        self.enabled = False
        self.database_configuration = None

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
