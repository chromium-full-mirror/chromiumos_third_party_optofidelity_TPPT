"""
Copyright (c) 2020, OptoFidelity OY
Copyright (c) 2020, The Chromium OS Authors

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

from sqlalchemy import Column, Integer, Boolean, Float, ForeignKey, VARCHAR
from sqlalchemy.orm import backref, relation, relationship

import MeasurementDB as mDB
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
import TPPTcommon.containers as containers
from TPPTcommon.exceptions import GridCreationError, TipSelectionError
from TPPTcommon.grid import GridVisContainer
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)

# Database table name for the test case.
DB_TEST_TABLE_NAME = 'pinch_test'

# Database table name for the test results.
DB_RESULTS_TABLE_NAME = 'pinch_results'

# Database table indices associated with test case.
DB_TABLE_INDICES = [(DB_TEST_TABLE_NAME, 'test_id'), (DB_RESULTS_TABLE_NAME, 'gesture_id')]


class PinchTest(mDB.Base):
    __tablename__ = DB_TEST_TABLE_NAME

    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('test_item.id', ondelete='CASCADE'), nullable=False)
    test = relation(mDB.TestItem, backref=backref(DB_TEST_TABLE_NAME, order_by=id))

    center_x = Column(Float)
    center_y = Column(Float)

    finger_size = Column(Float)
    start_separation = Column(Float)
    end_separation = Column(Float)
    azimuth = Column(Float)


class PinchResults(mDB.Base):
    __tablename__ = DB_RESULTS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    gesture_id = Column(Integer, ForeignKey(DB_TEST_TABLE_NAME + '.id', ondelete='CASCADE'), nullable=False)
    line = relation(PinchTest, backref=backref(DB_RESULTS_TABLE_NAME, order_by=id))

    panel_x = Column(Float)
    panel_y = Column(Float)
    pressure = Column(Float)
    finger_id = Column(Integer)
    time = Column(Float)
    event = Column(Integer)


class Pinch(TestStep):
    """
    In this test case we perform pinches in various orientations in the center of the DUT.
    """

    def __init__(self, context):
        super().__init__('Pinch')

        self.context = context

        # If database_configuration is defined, the controls parameters will be overridden from database if possible
        self.database_configuration = PinchTestParameters

        sizes = sorted(list(context.tips_node.single_tips_by_size.keys()), key=float)

        self.controls.finger_size = ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.controls.num_fingers = 2
        self.controls.info['num_fingers'] = {'label': 'Number of Fingers', 'min': 2, 'max': 2}

        self.speed = 30.0

        self.max_separation = 30.0

    def execute(self):
        dut = self.context.get_active_dut()

        self.context.html("Running Pinch test for dut:%s" % dut)

        test_item = self.context.create_db_test_item("Pinch Test")

        measurement_pinches = self._create_grid(dut)

        self.context.set_robot_speed(self.speed)

        for index, pinch in enumerate(measurement_pinches):
            self.context.indicators.set_test_detail('Pinch', str(index + 1) + ' / ' + str(len(measurement_pinches)))

            continuous_measurement = self.context.create_continuous_measurement(pinch)
            continuous_measurement.start()

            dut.pinch(pinch.center_x, pinch.center_y, pinch.start_separation, pinch.end_separation,
                      pinch.azimuth, clearance=-2)

            continuous_measurement.end()

            touch_list = continuous_measurement.parse_data()

            gesture_id = self._create_gesture(pinch, test_item)
            self._save_measurement_data(gesture_id, touch_list)

            self.context.breakpoint()

        self.context.close_db_test_item(test_item)

    def _create_grid(self, dut):
        """
        Create grid of Pinches that define the geometry of the test case.
        :param dut: DUT where the grid is evaluated on.
        """
        if self.max_separation > dut.width or self.max_separation > dut.height:
            raise GridCreationError("Pinch is too wide for DUT")

        min_separation = self.context.get_min_separation(float(self.controls.finger_size))
        center_x = dut.width / 2
        center_y = dut.height / 2

        grid = []
        for azimuth in [0, 45, 90]:
            grid.append(containers.Pinch(center_x, center_y, min_separation, self.max_separation, azimuth))
            grid.append(containers.Pinch(center_x, center_y, self.max_separation, min_separation, azimuth))
        return grid

    def visualize_grid(self, dut):
        test_pattern = self._create_grid(dut)
        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), test_pattern, dut.name)

    def tip_is_valid(self):
        try:
            self.context.tips_node.select_tips_by_size(self.controls.finger_size, 2, check_only=True)
            return True
        except TipSelectionError as e:
            logger.error(str(e))
            return False

    def pattern_is_valid(self):
        dut = self.context.get_active_dut()
        try:
            _ = self._create_grid(dut)
            return True
        except GridCreationError as e:
            logger.error(str(e))
            return False

    def _create_gesture(self, pinch, test_item):
        """
        Create gesture and add to database.
        :return: id of created gesture.
        """
        test = PinchTest()

        test.center_x = pinch.center_x
        test.center_y = pinch.center_y
        test.start_separation = pinch.start_separation
        test.end_separation = pinch.end_separation
        test.azimuth = pinch.azimuth
        test.test_id = test_item.id
        test.finger_size = float(self.controls.finger_size)
        test.speed = self.speed

        self.context.db.add(test)

        return test.id

    def _save_measurement_data(self, gesture_id, touch_list):
        """
        Save pinch measurement to database.
        """

        db_list = []

        for test_result in touch_list:
            results = PinchResults()

            results.panel_x = float(test_result.panel_x)
            results.panel_y = float(test_result.panel_y)
            results.pressure = float(test_result.pressure)
            results.finger_id = int(test_result.finger_id)
            results.time = test_result.time
            results.event = test_result.event
            results.gesture_id = gesture_id

            db_list.append(results)

            self.context.add_dut_point(float(test_result.panel_x), float(test_result.panel_y))

        self.context.db.addAll(db_list)



class PinchTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'pinch_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_pinch_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
    num_fingers = Column(Integer)
