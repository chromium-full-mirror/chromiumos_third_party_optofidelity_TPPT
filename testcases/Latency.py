"""
Copyright (c) 2022, OptoFidelity OY
Copyright (c) 2022, The Chromium OS Authors

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

from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
from TPPTcommon.containers import Line
from TPPTcommon.exceptions import GridCreationError, TipSelectionError
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)


class Latency(TestStep):
    """
    In this test case we move a finger back and forth vertically on the touch device as it moves left to right, covering
    the whole area in vertical lines.  This is used by the WALT latency measurement device, which needs a finger to
    cross a laser beam repeatedly at a fixed speed.
    """

    def __init__(self, context):
        super().__init__('Latency', context)

        # If database_configuration is defined, the controls parameters will be overridden from database if possible
        self.database_configuration = LatencyTestParameters
        self.results_class = None

        sizes = list(map(str, sorted(context.tips_node.single_tips_by_size.keys())))

        self.controls.finger_size = sizes[0] if len(sizes) > 0 else ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.speed = 60.0
        self.num_passes = 30

    def _initial_setup(self, dut):
        border_width = 5.0 + float(self.controls.finger_size)
        self.context.set_robot_default_speed()
        dut.jump(border_width, border_width, dut.base_distance, dut.base_distance)
        self.context.set_robot_speed(self.speed)

    def _pre_gesture_setup(self, gesture, dut):
        pass

    def _execute_gesture(self, line, dut):
        dut.move(line.start_x, line.start_y, -0.5, azimuth=0)
        dut.move(line.end_x, line.end_y, -0.5, azimuth=0)

    def _create_grid(self, dut):
        border_width = 5.0 + float(self.controls.finger_size)
        if 2 * border_width > dut.width or 2 * border_width > dut.height:
            raise GridCreationError("DUT is too small for test")

        grid = []
        for i in range(self.num_passes):
            x_pos = border_width + i * (dut.width - border_width * 2) / (self.num_passes - 1)

            # Go down on even passes and up on odd passes
            start_y = border_width
            end_y = dut.height - border_width
            if (i % 2) == 1:
                start_y, end_y = end_y, start_y

            grid.append(Line(x_pos, start_y, 0, x_pos, end_y, 0))
        return grid

    def tip_is_valid(self):
        try:
            self.context.tips_node.select_tips_by_size(float(self.controls.finger_size), 1, check_only=True)
            return True
        except TipSelectionError as e:
            logger.error(str(e))
            return False

    def _create_gesture(self, line, test_item):
        pass


class LatencyTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'latency_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_latency_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
