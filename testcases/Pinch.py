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

from optofidelity_protocols.measurementdb import PinchTest, PinchResults
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
import TPPTcommon.containers as containers
from TPPTcommon.exceptions import GridCreationError, TipSelectionError
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)


class Pinch(TestStep):
    """
    In this test case we perform pinches in various orientations in the center of the DUT.
    """

    def __init__(self, context):
        super().__init__('Pinch', context)

        # If database_configuration is defined, the controls parameters will be overridden from database if possible
        self.database_configuration = PinchTestParameters
        self.results_class = PinchResults

        sizes = [str(key) for (key, value) in sorted(context.tips_node.single_tips_by_size.items()) if len(value) >= 2]

        self.controls.finger_size = sizes[0] if len(sizes) > 0 else ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.controls.num_fingers = 2
        self.controls.info['num_fingers'] = {'label': 'Number of Fingers', 'min': 2, 'max': 2}

        self.speed = 30.0

        self.max_separation = 30.0

    def _pre_gesture_setup(self, pinch, dut):
        self.context.set_robot_default_speed()
        dut.jump(pinch.center_x, pinch.center_y, dut.base_distance, dut.base_distance)
        self.context.set_robot_speed(self.speed)

    def _execute_gesture(self, pinch, dut):
        dut.pinch(pinch.center_x, pinch.center_y, pinch.start_separation, pinch.end_separation,
                  pinch.azimuth, clearance=-2)

    def _create_grid(self, dut):
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

    def tip_is_valid(self):
        try:
            self.context.tips_node.select_tips_by_size(float(self.controls.finger_size), 2, check_only=True)
            return True
        except TipSelectionError as e:
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


class PinchTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'pinch_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_pinch_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
    num_fingers = Column(Integer)
