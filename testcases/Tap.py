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
from sqlalchemy.orm import relationship

from MeasurementDB import TapTest, TapResults
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
import TPPTcommon.containers as containers
from TPPTcommon.exceptions import GridCreationError, TipSelectionError
from TPPTcommon.grid import create_multi_finger_tap_grid, GridVisContainer
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)


class Tap(TestStep):
    """
    In this test case we perform single-finger and multi-finger taps at various locations and orientations.
    """

    def __init__(self, context):
        super().__init__('Tap')

        self.context = context

        self.database_configuration = TapTestParameters

        single_sizes = [str(key) for (key, value) in sorted(context.tips_node.single_tips_by_size.items())
                        if len(value) >= 2]

        multi_sizes = list(map(str, sorted(context.tips_node.multi_tips_by_size.keys())))

        self.controls.single_size = single_sizes[0] if len(single_sizes) > 0 else ""
        self.controls.info['single_size'] = {'label': 'Single finger size (mm)', 'items': single_sizes}

        self.controls.multi_size = multi_sizes[0] if len(multi_sizes) > 0 else ""
        self.controls.info['multi_size'] = {'label': 'Multi finger size (mm)', 'items': multi_sizes}

        self.controls.edge_width = 5.0
        self.controls.info['edge_width'] = {'label': 'Distance from edge (mm)'}

    def execute(self):
        dut = self.context.get_active_dut()

        base_distance = dut.base_distance

        self.context.html("Running Tap test for dut:%s" % dut)

        test_item = self.context.create_db_test_item("Tap Test")

        measurement_taps = self._create_grid(dut)

        for index, tap in enumerate(measurement_taps):
            self.context.indicators.set_test_detail('Tap', str(index + 1) + ' / ' + str(len(measurement_taps)))

            size = float(self.controls.multi_size if tap.fingers >= 3 else self.controls.single_size)
            self.context.tips_node.select_tips_by_size(size, tap.fingers)

            # Jump over DUT without specific jump height to avoid problems in case tip was changed.
            if index == 0 or tap.fingers != measurement_taps[index - 1].fingers:
                dut.jump(0.0, 0.0, base_distance)

            continuous_measurement = self.context.create_continuous_measurement(tap)
            continuous_measurement.start()

            if tap.fingers == 2:
                self.context.robot.set_finger_separation(tap.finger_distance)

            # TODO (seobrien): If two-finger dut.tap() robot client behavior is corrected, use that gesture instead
            dut.move(tap.x, tap.y, base_distance, azimuth=tap.angle)
            dut.move(tap.x, tap.y, -2, azimuth=tap.angle)
            dut.move(tap.x, tap.y, base_distance, azimuth=tap.angle)

            continuous_measurement.end()

            touch_list = continuous_measurement.parse_data()

            gesture_id = self._create_gesture(tap, test_item, size)

            self._save_measurement_data(gesture_id, touch_list)

            self.context.breakpoint()

        self.context.close_db_test_item(test_item)

    def _create_grid(self, dut):
        """
        Create grid of taps that define the geometry of the test case.
        :param dut: DUT where the grid is evaluated on.
        """
        grid = []

        # One finger
        xs = [self.controls.edge_width, dut.width / 2, dut.width - self.controls.edge_width]
        ys = [self.controls.edge_width, dut.height / 2, dut.height - self.controls.edge_width]
        for x in xs:
            for y in ys:
                grid.append(containers.Point(x, y, 0, fingers=1))

        # Two fingers
        separation = self.context.get_min_separation(float(self.controls.single_size))
        grid.extend(create_multi_finger_tap_grid(dut, 2, separation))

        # More fingers
        for count in [3, 4, 5]:
            tip_node = self.context.tips_node.get_multi_finger_tip_node(float(self.controls.multi_size), count)
            grid.extend(create_multi_finger_tap_grid(dut, count, tip_node.tnt_tip.tip_distance))

        return grid

    def visualize_grid(self, dut):
        test_pattern = self._create_grid(dut)
        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), test_pattern, dut.name)

    def tip_is_valid(self):
        try:
            self.context.tips_node.select_tips_by_size(float(self.controls.single_size), 2, check_only=True)
            for count in [3, 4, 5]:
                self.context.tips_node.select_tips_by_size(float(self.controls.multi_size), count, check_only=True)
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

    def _create_gesture(self, tap, test_item, size):
        """
        Create gesture and add to database.
        :return: id of created gesture.
        """
        test = TapTest()

        test.tap_x = tap.x
        test.tap_y = tap.y
        test.separation = tap.finger_distance
        test.azimuth = tap.angle
        test.num_fingers = tap.fingers
        test.finger_size = size
        test.edge_width = self.controls.edge_width
        test.test_id = test_item.id

        self.context.db.add(test)

        return test.id

    def _save_measurement_data(self, gesture_id, touch_list):
        """
        Save tap measurement to database.
        """
        db_list = []

        for test_result in touch_list:
            results = TapResults()

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


class TapTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'tap_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_tap_configurations')

    enabled = Column(Boolean)
    single_size = Column(VARCHAR(40))
    multi_size = Column(VARCHAR(40))
    edge_width = Column(Float)

