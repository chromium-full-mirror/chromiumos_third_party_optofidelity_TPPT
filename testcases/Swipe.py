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

from optofidelity_protocols.measurementdb import SwipeTest, SwipeResults
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
from TPPTcommon.exceptions import TipSelectionError
from TPPTcommon.grid import create_multi_swipe_horizontal, create_multi_swipe_vertical, create_multi_swipe_diagonal
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)


class Swipe(TestStep):
    """
    In this test case we perform fast swipes across the DUT using one or two fingers, which approach the touch
    surface while already in motion.
    """

    def __init__(self, context):
        super().__init__('Swipe', context)

        # If database_configuration is defined, the controls parameters will be overridden from database if possible
        self.database_configuration = SwipeTestParameters
        self.results_class = SwipeResults

        sizes = list(map(str, sorted(context.tips_node.single_tips_by_size.keys())))

        self.controls.finger_size = sizes[0] if len(sizes) > 0 else ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.controls.num_fingers = 1
        self.controls.info['num_fingers'] = {'label': 'Number of Fingers', 'min': 1, 'max': 2}

        self.controls.finger_clearance = 10.0
        self.controls.info['finger_clearance'] = {'label': 'Clearance between fingers (mm)'}

        self.speed = 300.0

    def _pre_gesture_setup(self, line, dut):
        self.context.set_robot_default_speed()
        dut.jump(line.start_x, line.start_y, dut.base_distance, dut.base_distance)
        self.context.set_robot_speed(self.speed)

    def _execute_gesture(self, line, dut):
        separation = self._get_finger_separation(self.controls.finger_clearance, float(self.controls.finger_size))
        self.context.robot.set_finger_separation(separation)
        dut.swipe(line.start_x, line.start_y, line.end_x, line.end_y, clearance=-2, radius=20,
                  azimuth1=line.angle, azimuth2=line.angle)

    def _create_grid(self, dut):
        separation = self._get_finger_separation(self.controls.finger_clearance, float(self.controls.finger_size))
        border_width = 10.0

        grid = create_multi_swipe_horizontal(dut, self.controls.num_fingers, separation, border_width)
        grid.extend(create_multi_swipe_vertical(dut, self.controls.num_fingers, separation, border_width))
        grid.extend(create_multi_swipe_diagonal(dut, self.controls.num_fingers, separation, border_width))

        return grid

    def tip_is_valid(self):
        # TODO: allow multiple fingers when support is added in robot client
        if self.controls.num_fingers > 1:
            logger.error("Swipes with more than one finger are not yet supported.")
            return False

        try:
            self.context.tips_node.select_tips_by_size(float(self.controls.finger_size), self.controls.num_fingers,
                                                       check_only=True)
            return True
        except TipSelectionError as e:
            logger.error(str(e))
            return False

    def _create_gesture(self, line, test_item):
        separation = self._get_finger_separation(self.controls.finger_clearance, float(self.controls.finger_size))
        test = SwipeTest()

        test.start_x = line.start_x
        test.start_y = line.start_y
        test.end_x = line.end_x
        test.end_y = line.end_y
        test.separation = separation
        test.azimuth = line.angle
        test.test_id = test_item.id
        test.num_fingers = line.fingers
        test.finger_size = float(self.controls.finger_size)
        test.swipe_speed = self.speed

        self.context.db.add(test)

        return test.id


class SwipeTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'swipe_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_swipe_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
    num_fingers = Column(Integer)
    finger_clearance = Column(Float)
