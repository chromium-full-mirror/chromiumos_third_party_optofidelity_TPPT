"""
Copyright (c) 2023, OptoFidelity OY
Copyright (c) 2023, The Chromium OS Authors

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

from optofidelity_protocols.measurementdb import ForceHysteresisTest, ForceHysteresisResults
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
import TPPTcommon.containers as containers
from TPPTcommon.exceptions import TipSelectionError
from TPPTcommon.grid import create_multi_finger_tap_grid
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)


class ForceHysteresis(TestStep):
    """
    This test performs a check for hysteresis in touchpad force reporting. For each measurement, we choose a location
    and a test force level. The robot will perform three force-presses for the measurement:
     (1) at the test force level
     (2) at a high force (500g)
     (3) again at the test force level
    """

    def __init__(self, context):
        super().__init__('Force Hysteresis', context)

        self.database_configuration = ForceHysteresisTestParameters
        self.results_class = ForceHysteresisResults
        self.measurement_timeout = 6.0

        sizes = list(map(str, sorted(context.tips_node.single_tips_by_size.keys())))

        self.controls.finger_size = sizes[0] if len(sizes) > 0 else ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.controls.edge_width = 10.0
        self.controls.info['edge_width'] = {'label': 'Distance from edge (mm)'}

        self.speed = 50.0
        self.high_force = 500.0
        self.test_forces = [70.0, 120.0, 170.0]

    def _pre_gesture_setup(self, gesture, dut):
        _, tap = gesture
        self.context.set_robot_default_speed()
        dut.jump(tap.x, tap.y, dut.base_distance, dut.base_distance)
        self.context.set_robot_speed(self.speed)

    def _execute_gesture(self, gesture, dut):
        force, tap = gesture
        dut.press(tap.x, tap.y, force, press_depth=-2.4)
        dut.press(tap.x, tap.y, self.high_force, press_depth=-2.4)
        dut.press(tap.x, tap.y, force, press_depth=-2.4)
        self.context.set_robot_default_speed()

    def _create_grid(self, dut):
        grid = []

        xs = [self.controls.edge_width, dut.width / 2, dut.width - self.controls.edge_width]
        ys = [self.controls.edge_width, dut.height / 2, dut.height - self.controls.edge_width]
        for force in self.test_forces:
            for x in xs:
                for y in ys:
                    grid.append((force, containers.Point(x, y, 0, fingers=1)))

        return grid

    def tip_is_valid(self):
        try:
            self.context.tips_node.select_tips_by_size(float(self.controls.finger_size), 1, check_only=True)
            return True
        except TipSelectionError as e:
            logger.error(str(e))
            return False

    def _create_gesture(self, gesture, test_item):
        """
        Create gesture and add to database.
        :return: id of created gesture.
        """
        force, tap = gesture
        test = ForceHysteresisTest()

        test.tap_x = tap.x
        test.tap_y = tap.y
        test.finger_size = self.controls.finger_size
        test.high_force = self.high_force
        test.force = force
        test.test_id = test_item.id

        self.context.db.add(test)

        return test.id


class ForceHysteresisTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'force_hysteresis_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_force_hysteresis_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
    edge_width = Column(Float)

