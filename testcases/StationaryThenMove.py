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
from TPPTcommon.exceptions import GridCreationError, TipSelectionError
from TPPTcommon.grid import GridVisContainer, create_center_to_edge_lines, create_center_to_corner_lines
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)

# Database table name for the test case.
DB_TEST_TABLE_NAME = 'stationary_then_move_test'

# Database table name for the test results.
DB_RESULTS_TABLE_NAME = 'stationary_then_move_results'

# Database table indices associated with test case.
DB_TABLE_INDICES = [(DB_TEST_TABLE_NAME, 'test_id'), (DB_RESULTS_TABLE_NAME, 'gesture_id')]


class StationaryThenMoveTest(mDB.Base):
    __tablename__ = DB_TEST_TABLE_NAME

    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('test_item.id', ondelete='CASCADE'), nullable=False)
    test = relation(mDB.TestItem, backref=backref(DB_TEST_TABLE_NAME, order_by=id))

    start_x = Column(Float)
    start_y = Column(Float)
    end_x = Column(Float)
    end_y = Column(Float)

    finger_size = Column(Float)
    swipe_speed = Column(Float)


class StationaryThenMoveResults(mDB.Base):
    __tablename__ = DB_RESULTS_TABLE_NAME

    id = Column(Integer, primary_key=True)
    gesture_id = Column(Integer, ForeignKey(DB_TEST_TABLE_NAME + '.id', ondelete='CASCADE'), nullable=False)
    line = relation(StationaryThenMoveTest, backref=backref(DB_RESULTS_TABLE_NAME, order_by=id))

    panel_x = Column(Float)
    panel_y = Column(Float)
    pressure = Column(Float)
    finger_id = Column(Integer)
    time = Column(Float)
    event = Column(Integer)


class StationaryThenMove(TestStep):
    """
    In this test we place a finger and keep it stationary for a moment before moving.
    All gestures start at the center of the touch surface, wait one second, then move
    to a corner or edge.
    """

    def __init__(self, context):
        super().__init__('Stationary Then Move')

        self.context = context

        self.database_configuration = StationaryThenMoveTestParameters

        sizes = list(map(str, sorted(context.tips_node.single_tips_by_size.keys())))

        self.controls.finger_size = sizes[0] if len(sizes) > 0 else ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.controls.swipe_speed = 100.0
        self.controls.info['swipe_speed'] = {'label': 'Speed (mm/s)', 'min': 10.0}

    def execute(self):
        dut = self.context.get_active_dut()

        base_distance = dut.base_distance

        self.context.html("Running Stationary Then Move test for dut:%s" % dut)

        test_item = self.context.create_db_test_item("Stationary Then Move Test")

        measurement_lines = self._create_grid(dut)

        for index, line in enumerate(measurement_lines):
            self.context.indicators.set_test_detail('Line', str(index + 1) + ' / ' + str(len(measurement_lines)))

            self.context.set_robot_default_speed()
            dut.jump(line.start_x, line.start_y, base_distance, base_distance)

            self.context.set_robot_speed(self.controls.swipe_speed)

            continuous_measurement = self.context.create_continuous_measurement(line)
            continuous_measurement.start()

            dut.drag(line.start_x, line.start_y, line.end_x, line.end_y, clearance=-2, predelay=1)

            continuous_measurement.end()

            touch_list = continuous_measurement.parse_data()

            gesture_id = self._create_gesture(line, test_item)

            self._save_measurement_data(gesture_id, touch_list)

            self.context.breakpoint()

        self.context.close_db_test_item(test_item)

    def _create_grid(self, dut):
        """
        Create grid of lines that define the geometry of the test case.
        :param dut: DUT where the grid is evaluated on.
        """
        border_width = 10.0

        grid = create_center_to_edge_lines(dut, border_width)
        grid.extend(create_center_to_corner_lines(dut, border_width))

        return grid

    def visualize_grid(self, dut):
        test_pattern = self._create_grid(dut)
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
        try:
            _ = self._create_grid(dut)
            return True
        except GridCreationError as e:
            logger.error(str(e))
            return False

    def _create_gesture(self, line, test_item):
        """
        Create gesture and add to database.
        :return: id of created gesture.
        """
        test = StationaryThenMoveTest()

        test.start_x = line.start_x
        test.start_y = line.start_y
        test.end_x = line.end_x
        test.end_y = line.end_y
        test.test_id = test_item.id
        test.finger_size = float(self.controls.finger_size)
        test.swipe_speed = self.controls.swipe_speed

        self.context.db.add(test)

        return test.id

    def _save_measurement_data(self, gesture_id, touch_list):
        """
        Save stationary then move measurement to database.
        """

        db_list = []

        for test_result in touch_list:
            results = StationaryThenMoveResults()

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


class StationaryThenMoveTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'stationary_then_move_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_stationary_then_move_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
    swipe_speed = Column(Float)
