"""
Copyright (c) 2020, OptoFidelity OY
Copyright (c) 2021, The Chromium OS Authors

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

from sqlalchemy import Boolean, Column, Integer, ForeignKey, VARCHAR
from sqlalchemy.orm import relationship

from optofidelity_protocols.measurementdb import SingleLineWithNoiseTest, SingleLineWithNoiseResults
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
from TPPTcommon.grid import create_multi_swipe_diagonal
from TPPTcommon.TestStep import NoiseTestStep

logger = logging.getLogger(__name__)


class SingleLineWithNoise(NoiseTestStep):
    """
    In this test case we draw a line from top left to bottom right of the test surface, applying a square wave
    of 10V through the tip, with frequencies between 0 and 500,000 Hz, in increments of 500 Hz.
    """

    def __init__(self, context):
        super().__init__('Single Line With Noise', context)

        self.database_configuration = SingleLineWithNoiseTestParameters
        self.results_class = SingleLineWithNoiseResults

    def _execute_gesture(self, gesture, dut):
        dut.drag(self.test_gesture.start_x, self.test_gesture.start_y, self.test_gesture.end_x, self.test_gesture.end_y,
                 clearance=-2, azimuth1=0, azimuth2=0, predelay=1)

    def _single_gesture_geometry(self, dut):
        grid = create_multi_swipe_diagonal(dut, 1, 0.0, 10.0)
        return grid[0]

    def _create_gesture(self, frequency, test_item):
        test = SingleLineWithNoiseTest()

        test.start_x = self.test_gesture.start_x
        test.start_y = self.test_gesture.start_y
        test.end_x = self.test_gesture.end_x
        test.end_y = self.test_gesture.end_y
        test.test_id = test_item.id
        test.finger_size = float(self.controls.finger_size)
        test.frequency = frequency

        self.context.db.add(test)

        return test.id


class SingleLineWithNoiseTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'single_line_with_noise_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_single_line_with_noise_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
    freq_step = Column(Integer)
    device_path = Column(VARCHAR(40))
