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
import os
import pymysql
from sqlalchemy import Column, Integer, ForeignKey, VARCHAR, create_engine, UniqueConstraint
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy.ext.declarative import declarative_base
from ruamel.yaml import YAML
from scriptpath import join_script_root_directory

import logging
logger = logging.getLogger(__name__)

CONFIGURATION_PATH = join_script_root_directory('dbconfig.yaml')

class ConfigurationDatabase:
    TestConfigBase = declarative_base()
    configuration = []

    engine = None
    session_maker = sessionmaker()
    Session = scoped_session(session_maker)

    @classmethod
    def initialize_configuration_database(cls):
        '''
        Initializes database based on the configuration given in
        CONFIGURATION_PATH
        :return: True if database is initialized, False if not
                (the database is disabled by configuration)
        '''
        try:
            cls.configuration = ConfigurationDatabase.read_configuration(CONFIGURATION_PATH)
        except FileNotFoundError as e:
            raise e

        if not cls.configuration['database_enabled']:
            return False

        host_data = {'database_engine': cls.configuration['database_engine'],
                     'address': cls.configuration['host_name'],
                     'port': cls.configuration['port'],
                     'user_name': cls.configuration['user_name'],
                     'password': cls.configuration['password'],
                     'schema': cls.configuration['database']}

        cls.engine = create_engine(
            '{database_engine}://{user_name}:{password}@{address}:{port}/{schema}'.format(**host_data))

        cls.session_maker.configure(bind=cls.engine)
        # Bind the metadata to the engine to allow table creation later on when initializing LoopSequence.Context
        cls.TestConfigBase.metadata.bind = cls.engine

        if not ConfigurationDatabase.duplicate_procedure_exists():
            ConfigurationDatabase.create_duplicate_procedure()

        return True

    @staticmethod
    def duplicate_procedure_exists():
        """
        Query the database schema to check if the duplicate procedure exists
        :return: 1 or None (True or False)
        """
        sql = \
            'SELECT 1 \
            FROM information_schema.routines \
            WHERE routine_type = "PROCEDURE" \
            AND routine_name = "duplicate_configuration_group" \
            AND routine_schema = "{}";'.format(ConfigurationDatabase.configuration['database'])

        exists = ConfigurationDatabase.engine.execute(sql).scalar()

        return exists

    @staticmethod
    def create_duplicate_procedure():
        """
        Execute the duplicate procedure creation SQL statements from a file
        """
        file_directory = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
        with open(os.path.join(file_directory,'duplicate_configuration_group_procedure.sql'), 'r') as file:
            sql = file.read()
            ConfigurationDatabase.engine.execute(sql)

    @staticmethod
    def load_configuration_names_for_group(group_name=''):
        """
        Load the configuration names to populate the configuration dropdown in the UI
        :param group_name: The desired group name for which to fetch the names
        :return: List of the configuration names
        """
        configuration_names = ['']
        session = ConfigurationDatabase.Session()

        result = session.query(TestConfigurationGroup.id) \
            .filter(TestConfigurationGroup.name == group_name) \
            .one_or_none()

        group_id = result.id if result is not None else None

        try:
            for row in session.query(TestConfiguration).filter(TestConfiguration.configuration_group == group_id):
                configuration_names.append(row.name)
        finally:
            session.close()

        return configuration_names

    @staticmethod
    def load_configurations_by_group_name(group_name='', test_parameter_classes=[]):
        """
        Returns all enabled test step configurations that are in the named configuration group

        :param group_name: The desired configuration group name
        :param test_parameter_classes: List of configurable test step database configuration classes
        :return: List of TestConfiguration-objects
        """

        num_retrys = 10

        # Retry loading config group in case there is any kind of error such as SQL server closing connection.
        for i in range(num_retrys):
            try:
                session = ConfigurationDatabase.Session()
                all_configurations = []

                # Query all the different TestConfigurations and join them together for sorting later
                try:
                    for parameter_class in test_parameter_classes:
                        parameter_configurations = session.query(parameter_class) \
                            .join(parameter_class._test_configuration_orm) \
                            .join(TestConfiguration._configuration_group_orm) \
                            .filter(TestConfigurationGroup.name == group_name) \
                            .filter(parameter_class.enabled == 1) \
                            .all()

                        all_configurations += parameter_configurations
                finally:
                    session.close()

                return all_configurations
            except Exception as e:
                if i < num_retrys - 1:
                    logger.warning("Loading config group failed: " + str(e) + " Retrying ...")
                else:
                    raise e

    @staticmethod
    def create_new_configuration_group(group_name):
        session = ConfigurationDatabase.Session()

        test_configuration_group = TestConfigurationGroup()
        test_configuration_group.name = group_name

        try:
            session.add(test_configuration_group)
            session.commit()
        except:
            session.rollback()
        finally:
            session.close()

    @staticmethod
    def delete_configuration_group(group_name):
        session = ConfigurationDatabase.Session()

        try:
            session.query(TestConfigurationGroup).filter(TestConfigurationGroup.name == group_name).delete()
            session.commit()
        except:
            session.rollback()
        finally:
            session.close()

    @staticmethod
    def delete_configuration(configuration_name):
        session = ConfigurationDatabase.Session()

        try:
            session.query(TestConfiguration).filter(TestConfiguration.name == configuration_name).delete()
            session.commit()
        except:
            session.rollback()
        finally:
            session.close()

    @staticmethod
    def duplicate_configuration_group(active_group_name, new_group_name):
        """
        Duplicates a configuration group and related configurations and test parameters
        The work is done inside a stored procedure on the SQL server
        :param active_group_name: The name of the current configuration group to be copied
        :param new_group_name: Name for the new duplicated group that is inserted
        """

        # Use pymysql instead of sqlalchemy because the procedure must be called outside transactional context
        # when the procedure contains temporary table CREATEs and DROPs.
        # Using pymysql-connection with autocommit on we can call the procedure from the script
        connection = pymysql.connect(host=ConfigurationDatabase.configuration['host_name'],
                                     user=ConfigurationDatabase.configuration['user_name'],
                                     passwd=ConfigurationDatabase.configuration['password'],
                                     db=ConfigurationDatabase.configuration['database'])
        connection.autocommit(True)
        
        cursor = connection.cursor()
        cursor.callproc('duplicate_configuration_group', (active_group_name, new_group_name,))

        cursor.close()
        connection.close()

    @staticmethod
    def load_configuration_group_names():
        configuration_group_names = ['']
        session = ConfigurationDatabase.Session()

        try:
            for row in session.query(TestConfigurationGroup):
                configuration_group_names.append(row.name)
        finally:
            session.close()

        return configuration_group_names

    @staticmethod
    def create_and_insert_new_configuration(configuration_group, configuration_name, session):
        """
        Creates a new configuration in the database. Takes in the session-object because we will revert
        the whole configuration saving process if an exception occurs anywhere during the saving process

        :return: The generated id for the new configuration
        """
        new_test_configuration = TestConfiguration()
        new_test_configuration.name = configuration_name

        configuration_group_result = session.query(TestConfigurationGroup.id) \
            .filter(TestConfigurationGroup.name == configuration_group) \
            .one_or_none()

        configuration_group_id = \
            configuration_group_result.id if configuration_group_result is not None else None

        new_test_configuration.configuration_group = configuration_group_id
        session.add(new_test_configuration)

        # Flush the session to the server so that the new_test_configuration objects gets the autoincremented id
        session.flush()

        return new_test_configuration.id

    @staticmethod
    def read_configuration(configuration_path):
        _yaml = YAML(typ='safe')
        with open(configuration_path, 'r') as file:
            config = _yaml.load(file)

        def convert_to_default_types(v):
            if v.__class__.__name__ == 'CommentedSeq':
                r = [convert_to_default_types(a) for a in list(v)]
                return r
            if v.__class__.__name__ == 'CommentedMap':
                r = {}
                for n in v:
                    r[n] = convert_to_default_types(v[n])
                return r
            return v

        config = convert_to_default_types(config)

        return config


class TestConfiguration(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'test_configuration'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(VARCHAR(45), nullable=False)
    configuration_group = Column(Integer, ForeignKey('test_configuration_group.id', ondelete='CASCADE'))

    _configuration_group_orm = relationship('TestConfigurationGroup', back_populates='_test_configuration_orm')

    _jitter_configurations = \
        relationship('StationaryJitterStaticNoiseTestParameters', back_populates='_test_configuration_orm')

    _tapping_repeatability_configurations = \
        relationship('OneFingerTappingRepeatabilityTestParameters', back_populates='_test_configuration_orm')

    _linearity_configurations = \
        relationship('LinearityTestParameters', back_populates='_test_configuration_orm')

    _grid_accuracy_configurations = \
        relationship('GridAccuracyTestParameters', back_populates='_test_configuration_orm')

    __table_args__ = (UniqueConstraint('name', 'configuration_group', name='_name_group_uc'),)


class TestConfigurationGroup(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'test_configuration_group'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(VARCHAR(45), nullable=False, unique=True)

    _test_configuration_orm = relationship('TestConfiguration', back_populates='_configuration_group_orm')
