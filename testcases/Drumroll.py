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

from sqlalchemy import Column, Integer, Boolean, ForeignKey, VARCHAR
from sqlalchemy.orm import relationship

from MeasurementDB import DrumrollTest, DrumrollResults
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
from TPPTcommon.exceptions import GridCreationError, TipSelectionError
from TPPTcommon.grid import GridVisContainer, create_multi_finger_tap_grid
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)


class Drumroll(TestStep):
    """
    In this test case we perform drumroll gestures, where two fingers quickly tap, alternating fingers.
    """

    def __init__(self, context):
        super().__init__('Drumroll')

        self.context = context

        self.database_configuration = DrumrollTestParameters

        sizes = [str(key) for (key, value) in sorted(context.tips_node.single_tips_by_size.items()) if len(value) >= 2]

        self.controls.finger_size = sizes[0] if len(sizes) > 0 else ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.controls.num_fingers = 2
        self.controls.info['num_fingers'] = {'label': 'Number of Fingers', 'min': 2, 'max': 2}

        self.number_taps = 24

    def execute(self):
        dut = self.context.get_active_dut()

        self.context.html("Running Drumroll test for dut:%s" % dut)

        test_item = self.context.create_db_test_item("Drumroll Test")

        measurement_drumrolls = self._create_grid(dut)

        for index, drumroll in enumerate(measurement_drumrolls):
            self.context.indicators.set_test_detail('Drumroll', str(index + 1) + ' / ' + str(len(measurement_drumrolls)))

            continuous_measurement = self.context.create_continuous_measurement(drumroll)
            continuous_measurement.start()

            dut.drumroll(drumroll.x, drumroll.y, drumroll.angle, drumroll.finger_distance, self.number_taps, 2,
                         clearance=-2)

            continuous_measurement.end()

            touch_list = continuous_measurement.parse_data()

            gesture_id = self._create_gesture(drumroll, test_item)
            self._save_measurement_data(gesture_id, touch_list)

            self.context.breakpoint()

        self.context.close_db_test_item(test_item)

    def _create_grid(self, dut):
        """
        Create grid of taps that define the geometry of the test case.
        :param dut: DUT where the grid is evaluated on.
        """
        separation = self.context.get_min_separation(float(self.controls.finger_size))
        return create_multi_finger_tap_grid(dut, 2, separation)

    def visualize_grid(self, dut):
        test_pattern = self._create_grid(dut)
        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), test_pattern, dut.name)

    def tip_is_valid(self):
        try:
            self.context.tips_node.select_tips_by_size(float(self.controls.finger_size), 2, check_only=True)
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

    def _create_gesture(self, drumroll, test_item):
        """
        Create gesture and add to database.
        :return: id of created gesture.
        """
        test = DrumrollTest()

        test.center_x = drumroll.x
        test.center_y = drumroll.y
        test.separation = drumroll.finger_distance
        test.azimuth = drumroll.angle
        test.test_id = test_item.id
        test.finger_size = float(self.controls.finger_size)
        test.number_taps = self.number_taps

        self.context.db.add(test)

        return test.id

    def _save_measurement_data(self, gesture_id, touch_list):
        """
        Save drumroll measurement to database.
        """
        db_list = []

        for test_result in touch_list:
            results = DrumrollResults()

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



class DrumrollTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'drumroll_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_drumroll_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
    num_fingers = Column(Integer)
