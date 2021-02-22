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
import logging
import queue
import time

logger = logging.getLogger(__name__)

class TapMeasurementDeviceSocket(TapMeasurement):
    '''
    Tap measurement from device socket (TCP).
    '''

    def __init__(self, indicators, point, dsock):
        super(TapMeasurementDeviceSocket, self).__init__(indicators, point)

        self.dsock = dsock

    def _start(self):
        # Clear queue before launching the measurement thread.
        self.dsock.clear_queue()

    def _read_results(self):
        # Wait for the first event from the device and store that as result. Returns empty list if timeout occurs.
        self.results = self.dsock.ReturnP2PArray(timeout=self.timeout)

class ContinuousMeasurementDeviceSocket(ContinuousMeasurement):
    '''
    Continuous measurement from device socket (TCP).
    '''

    def __init__(self, indicators, line, dsock):
        super(ContinuousMeasurementDeviceSocket, self).__init__(indicators, line)

        self.dsock = dsock

    def _start(self):
        # Clear queue before launching the measurement thread.
        self.dsock.clear_queue()

    def _read_results(self):
        try:
            start_time = time.time()
            # Read first event with timeout that should be sufficiently long for effector to reach DUT surface.
            item = self.dsock.queue.get(timeout=self.start_timeout)
            self.dsock.queue.task_done()

            if item is None:
                return

            self.results.append(item)

            # Read events until timeout is exceeded
            for touch in self.dsock.CLine(timeout=self.timeout):
                self.results.append(touch)
                if time.time() - start_time > self.max_time:
                    logger.warn("Measurement time exceeded {} seconds. Stopping measurement.".format(self.max_time))
                    return
        except queue.Empty:
            pass # There was no event reported within timeout. This ends the measurement.