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


class Indicators:
    """
    Indicators to show in UI.
    Indicators consist of name-value-pairs that are shown in UI with some fixed style.
    """

    def __init__(self, ui):
        self._ui = ui
        self._status = ""
        self._dut_name = ""
        self._tip_name = ""
        self._test_details = []
        self.X = ""
        self.Y = ""

    def set_dut_name(self, dut_name):
        self._dut_name = dut_name
        self.update_ui()

    def set_tip_name(self, tip_name):
        self._tip_name = tip_name
        self.update_ui()

    def set_status(self, status):
        self._status = status
        self.update_ui()

    def set_test_detail(self, name, value):
        self.set_test_details([(name, value)])

    def set_test_details(self, test_details):
        self._test_details.clear()

        for t in test_details:
            self._test_details.append("<b>" + t[0] + "</b>: " + t[1] + "<br>")

        self.update_ui()

    def get_status(self):
        return self._status

    def update_ui(self):
        text = "<b>Status</b>: " + self._status + "<br>"
        text += "<b>DUT</b>: " + self._dut_name + "<br>"
        text += "<b>Tip</b>: " + self._tip_name + "<br>"

        for t in self._test_details:
            text += t

        self._ui.set_indicators(text)