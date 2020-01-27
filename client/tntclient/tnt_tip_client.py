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
from .tnt_client import TnTClientObject, RequestError
from . import logger

log = logger.get_logger(__name__)


class TnTTipClient(TnTClientObject):
    """ This class implements methods to control TnT Server tip resources. """

    def __init__(self, name, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        TnTClientObject.__init__(self, host, port, workspace, 'tip', name)

        self._data = None
        self._parsed_data = None

        try:
            self._refresh_data()
        except RequestError as err:
            raise RuntimeError("Could not initialize Tip client: " + str(err))

        self._robot = None

    def _get_tip_data(self, name):
        self._refresh_data()
        return self._parsed_data[name]

    def _refresh_data(self):
        """ Updates Tip information from the server. """
        self._data = self._GET("")["properties"]

        self._parsed_data = {}
        self._parsed_data["slot_in"] = self._data["slot_in"]
        self._parsed_data["slot_out"] = self._data["slot_out"]
        self._parsed_data["diameter"] = self._data["diameter"]
        self._parsed_data["dimension"] = self._data["dimension"]
        self._parsed_data["model"] = self._data["model"]
        self._parsed_data["num_tips"] = self._data["num_tips"]
        self._parsed_data["tip_distance"] = self._data["tip_distance"]
        self._parsed_data["separation"] = self._data["separation"]
        self._parsed_data["first_finger_offset"] = self._data["first_finger_offset"]

    @property
    def slot_in(self):
        """ Tip's slot-in position in workspace context. In this position tip is fixed to a rack. """
        return self._get_tip_data("slot_in")

    @property
    def slot_out(self):
        """ Tip's slot-out position in workspace context. In this position tip is free from a rack. """
        return self._get_tip_data("slot_out")

    @property
    def diameter(self):
        """ Diameter of the tip. """
        return self._get_tip_data("diameter")

    @property
    def length(self):
        """ Length of the tip. """
        return self._get_tip_data("dimension")["z"]

    @property
    def is_multifinger(self):
        """ Is tip multifinger. """
        return self._get_tip_data("model") == "Multifinger"

    @property
    def num_tips(self):
        """ Number of tips in multifinger. """
        return self._get_tip_data("num_tips")

    @property
    def tip_distance(self):
        """ Axial distance of adjacent tips in multifinger. """
        return self._get_tip_data("tip_distance")

    @property
    def separation(self):
        """ Separation of two-finger tool required to pick multifinger. """
        return self._get_tip_data("separation")

    @property
    def first_finger_offset(self):
        """ Distance from the middle of multifinger tip to the first finger. """
        return self._get_tip_data("first_finger_offset")
