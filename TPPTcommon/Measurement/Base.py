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
from optofidelity_protocols.dut import Measurement
from threading import Thread


class TapMeasurement():
    '''
    Base class for tap measurement context.
    Test cases make tap measurements based on methods defined here.
    '''

    def __init__(self, indicators, point):
        self.indicators = indicators
        self.point = point
        self.results = None
        self.timeout = 1.0
        self.thread = Thread(target=self._thread_main)

    def start(self, timeout=6.0):
        # Initialize members used in tap measurement.
        self.timeout = timeout
        self.results = []

        self._start()

        self.thread.start()

    def end(self):
        self.thread.join()

    def _start(self):
        pass

    def _thread_main(self):
        self._read_results()
        self._update_tap_coordinate_indicators()

    def _read_results(self):
        pass

    def _update_tap_coordinate_indicators(self):
        if self.results != []:
            self.indicators.X = self.results[0][0]
            self.indicators.Y = self.results[0][1]
        else:
            self.indicators.X = '-'
            self.indicators.Y = '-'

class ContinuousMeasurement():
    '''
    Base class for continuous measurement (e.g. swipe) context.
    Test cases make continuous measurements based on methods defined here.
    '''

    def __init__(self, indicators, line):
        self.indicators = indicators
        self.line = line
        self.timeout = 0.5
        self.start_timeout = 6.0
        self.results = None
        self.thread = Thread(target=self._thread_main)

    def start(self, timeout=0.5, start_timeout=6.0):
        '''
        Start continuous measurement in a separate thread.
        :param timeout: Timeout in seconds between consecutive measurements.
        :param start_timeout: Timeout in seconds for the first measurement.
        '''

        self.timeout = timeout
        self.start_timeout = start_timeout
        self.results = []

        self._start()

        self.thread.start()

    def end(self):
        self.thread.join()

        # Show last measured point in UI.
        self._update_line_coordinate_indicators()

    def _start(self):
        pass

    def _thread_main(self):
        self._read_results()
        self._update_line_coordinate_indicators()

    def _read_results(self):
        pass

    def _update_line_coordinate_indicators(self):
        if self.results != []:
            self.indicators.X = self.results[-1][0][0]
            self.indicators.Y = self.results[-1][0][1]
        else:
            self.indicators.X = '-'
            self.indicators.Y = '-'

    def parse_data(self):
        results = self.results
        touchlist = []
        #last_coord = []
        if len(results) > 0:
            for cline_data in results:
                if "OK" in cline_data:
                    for point in range(cline_data.index("OK")):  # Read all data points before "OK"
                        touchlist.append(Measurement(*cline_data[point]))
        return touchlist

    def save_data_to_csv_file(self, line_id, file_path, write_header=False, replace_file=False):
        touchlist = self.parse_data()

        write_parameter = 'a'
        if replace_file:
            write_parameter = 'w'
        with open(file_path, write_parameter) as file:
            if write_header:
                Header = "Panel X,Panel Y,Panel Z,Finger ID,Timestamp_EXT,Timestamp_INT,Event,Line ID\n"
                file.write(Header)
            for testresult in touchlist:
                resultstring = str(testresult).strip("[]")
                file.write(resultstring + "," +str(line_id) +"\n")
