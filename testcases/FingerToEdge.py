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

from sqlalchemy import Column, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship


from optofidelity_protocols.measurementdb import FingerToEdgeTest, FingerToEdgeResults
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
from TPPTcommon.containers import Line
from TPPTcommon.TestStep import ManualTestStep


logger = logging.getLogger(__name__)


class FingerToEdge(ManualTestStep):
    """
    In this test case we draw a line from the center of the surface to each edge, going completely over the edge.
    """

    def __init__(self, context):
        super().__init__('Finger To Edge', context)
        self.results_class = FingerToEdgeResults

    @property
    def _instruction_text(self):
        return "Use a finger to draw a line from the CENTER to the {} edge, going completely over the edge."

    def _create_grid(self, dut):
        border_extension = 10.0

        center_x = dut.width / 2.0
        center_y = dut.height / 2.0
        grid = [
            ManualTestStep.Gesture(Line(center_x, center_y, 0, -border_extension, center_y, 0),
                                   ("LEFT",)),
            ManualTestStep.Gesture(Line(center_x, center_y, 0, dut.width + border_extension, center_y, 0),
                                   ("RIGHT",)),
            ManualTestStep.Gesture(Line(center_x, center_y, 0, center_x, -border_extension, 0),
                                   ("TOP",)),
            ManualTestStep.Gesture(Line(center_x, center_y, 0, center_x, dut.height + border_extension, 0),
                                   ("BOTTOM",))
        ]

        return grid

    def _create_gesture(self, gesture_tuple, test_item):
        line = gesture_tuple.gesture
        test = FingerToEdgeTest()

        test.start_x = line.start_x
        test.start_y = line.start_y
        test.end_x = line.end_x
        test.end_y = line.end_y
        test.test_id = test_item.id

        self.context.db.add(test)

        return test.id


class FingerToEdgeTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'finger_to_edge_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_finger_to_edge_configurations')

    enabled = Column(Boolean)
