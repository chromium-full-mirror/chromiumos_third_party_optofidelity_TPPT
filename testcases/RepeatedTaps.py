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

from MeasurementDB import RepeatedTapsTest, RepeatedTapsResults
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
import TPPTcommon.containers as containers
from TPPTcommon.exceptions import TipSelectionError
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)


class RepeatedTaps(TestStep):
    """
    In this test we perform many single-finger taps at several locations to test the consistency of measurements.
    """

    def __init__(self, context):
        super().__init__('Repeated Taps', context)

        self.database_configuration = RepeatedTapsTestParameters
        self.results_class = RepeatedTapsResults
        self.measurement_timeout = 6.0

        sizes = list(map(str, sorted(context.tips_node.single_tips_by_size.keys())))

        self.controls.finger_size = sizes[0] if len(sizes) > 0 else ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.controls.edge_width = 5.0
        self.controls.info['edge_width'] = {'label': 'Distance from edge (mm)'}

        self.controls.taps_per_location = 20
        self.controls.info['taps_per_location'] = {'label': 'Taps per location'}

    def _pre_gesture_setup(self, tap, dut):
        dut.jump(tap.x, tap.y, dut.base_distance, dut.base_distance)

    def _execute_gesture(self, tap, dut):
        for i in range(self.controls.taps_per_location):
            dut.tap(tap.x, tap.y, clearance=-2)

    def _create_grid(self, dut):
        grid = []

        xs = [self.controls.edge_width, dut.width / 2, dut.width - self.controls.edge_width]
        ys = [self.controls.edge_width, dut.height / 2, dut.height - self.controls.edge_width]
        for x in xs:
            for y in ys:
                grid.append(containers.Point(x, y, 0, fingers=1))

        return grid

    def tip_is_valid(self):
        try:
            self.context.tips_node.select_tips_by_size(float(self.controls.finger_size), 1, check_only=True)
            return True
        except TipSelectionError as e:
            logger.error(str(e))
            return False

    def _create_gesture(self, tap, test_item):
        """
        Create gesture and add to database.
        :return: id of created gesture.
        """
        test = RepeatedTapsTest()

        test.tap_x = tap.x
        test.tap_y = tap.y
        test.finger_size = float(self.controls.finger_size)
        test.edge_width = self.controls.edge_width
        test.number_taps = self.controls.taps_per_location
        test.test_id = test_item.id

        self.context.db.add(test)

        return test.id


class RepeatedTapsTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'repeated_taps_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_repeated_taps_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
    edge_width = Column(Float)
    taps_per_location = Column(Integer)

