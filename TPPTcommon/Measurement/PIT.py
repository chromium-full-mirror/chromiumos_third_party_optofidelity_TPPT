"""
Copyright (c) 2019, OptoFidelity OY

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
from .Base import *

class TapMeasurementPIT(TapMeasurement):
    '''
    Tap measurement from PIT box.
    Todo: Needs to be tested.
    '''

    def __init__(self, indicators, point, pit, dut_index):
        super(TapMeasurementPIT, self).__init__(indicators, point)

        self.pit = pit
        self.dut_index = dut_index

    def _start(self):
        pass

    def _read_results(self):
        try:
            self.results = self.pit.ReturnP2PArray(self.dut_index)
        except:
            pass # Todo: Which exception is this supposed to handle? Should only pass "no event" type of errors.

class ContinuousMeasurementPIT(ContinuousMeasurement):
    '''
    Continuous measurement from PIT box.
    Todo: Needs to be tested.
    '''

    def __init__(self, line, indicators, pit):
        super(ContinuousMeasurementPIT, self).__init__(indicators, line)

        self.pit = pit

    def _start(self):
        pass

    def _read_results(self):
        for touch in self.pit.CLine():
            self.results.append(touch)