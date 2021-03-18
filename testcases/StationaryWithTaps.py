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

from optofidelity_protocols.measurementdb import StationaryWithTapsTest, StationaryWithTapsResults
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
import TPPTcommon.containers as containers
from TPPTcommon.exceptions import TipSelectionError
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)


class StationaryWithTaps(TestStep):
    """
    In this test case we place one finger in the center of the DUT, and perform taps close to it with the other finger.
    """

    def __init__(self, context):
        super().__init__('Stationary With Taps', context)

        self.database_configuration = StationaryWithTapsTestParameters
        self.results_class = StationaryWithTapsResults

        sizes = [str(key) for (key, value) in sorted(context.tips_node.single_tips_by_size.items()) if len(value) >= 2]

        self.controls.finger_size = sizes[0] if len(sizes) > 0 else ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.controls.num_fingers = 2
        self.controls.info['num_fingers'] = {'label': 'Number of Fingers', 'min': 2, 'max': 2}

        self.controls.finger_clearance = 10.0
        self.controls.info['finger_clearance'] = {'label': 'Clearance between fingers (mm)'}

        self.speed = 3.0
        self.tap_azimuth_step = 8.0

    def _pre_gesture_setup(self, compass, dut):
        self.context.set_robot_default_speed()
        dut.jump(compass.center_x, compass.center_y, dut.base_distance, dut.base_distance)
        dut.move(compass.center_x, compass.center_y, dut.base_distance, azimuth=compass.start_azimuth)
        separation = self._get_finger_separation(self.controls.finger_clearance, float(self.controls.finger_size))
        self.context.robot.set_finger_separation(separation)
        self.context.set_robot_speed(self.speed)

    def _execute_gesture(self, compass, dut):
        dut.compass_tap(compass.center_x, compass.center_y, compass.start_azimuth, compass.end_azimuth,
                        compass.separation, self.tap_azimuth_step, tap_with_stationary_finger=False, clearance=-2)

    def _create_grid(self, dut):
        separation = self._get_finger_separation(self.controls.finger_clearance, float(self.controls.finger_size))

        center_x = dut.width / 2
        center_y = dut.height / 2

        grid = [
            containers.Compass(center_x, center_y, separation, 0, 179),
            containers.Compass(center_x, center_y, separation, 180, 359)
        ]
        return grid

    def tip_is_valid(self):
        try:
            self.context.tips_node.select_tips_by_size(float(self.controls.finger_size), 2, check_only=True)
            return True
        except TipSelectionError as e:
            logger.error(str(e))
            return False

    def _create_gesture(self, compass, test_item):
        """
        Create gesture and add to database.
        :return: id of created gesture.
        """
        test = StationaryWithTapsTest()

        test.center_x = compass.center_x
        test.center_y = compass.center_y
        test.separation = compass.separation
        test.start_azimuth = compass.start_azimuth
        test.end_azimuth = compass.end_azimuth
        test.test_id = test_item.id
        test.finger_size = float(self.controls.finger_size)
        test.tap_azimuth_step = self.tap_azimuth_step

        self.context.db.add(test)

        return test.id


class StationaryWithTapsTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'stationary_with_taps_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_stationary_with_taps_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
    num_fingers = Column(Integer)
    finger_clearance = Column(Float)
