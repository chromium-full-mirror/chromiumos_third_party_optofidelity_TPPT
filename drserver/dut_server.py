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
from .node import Node, json_out
from .dut import DutAPI


class DutServer(Node):
    """
    Dut communication server
    """
    static = None
    def __init__(self, name):
        super().__init__(name)
        DutServer.static = self

    def _init(self, **kwargs):
        host = kwargs.get("host", "127.0.0.1")

        # Port is hard-coded in DUT application.
        port = int(kwargs.get("port", 50008))
        self.dutapi = DutAPI(host, port, auth_key="optofidelitytouchtest0")

    def __del__(self):
        self.dutapi.close()

    def _dut_name_to_client_name(self, dut_name: str):
        """
        Map TnT Dut Name to Dut communication client name
        for example "Dut1" -> "Client1"
        All the communication with physical DUT is done using Client Name
        :return: mapped client name
        """
        client_names = [name for name in self.dutapi.clients]
        for client_name in client_names:
            info = self.info(client_name = client_name)
            name = info.get("dut_name", None)
            if name is not None and name == dut_name:
                return client_name
        raise(Exception("communication client not found for dut name {}".format(dut_name)))

    def clients(self):
        """
        List connected clients.
        :return: List of communication client names.
        """
        client_names = [name for name in self.dutapi.clients]
        return client_names

    def is_dut_connected(self, dut_name: str):
        try:
            # will raise exception if not found
            client_name = self._dut_name_to_client_name(dut_name)
        except:
            return False
        return client_name in self.clients()

    def info(self, dut_name: str=None, client_name: str=None):
        """
        Read raw info dict from DUT using DUT Name or Client Name
        :param dut_name: name of the DUT. (optional)
        :param client_name: name of the connected dut client. (optional)
        :return:
        """
        client_name = self._dut_name_to_client_name(dut_name) if client_name is None else client_name
        info = self.dutapi.get_info(client_name)
        return info

    def touches(self, dut_name: str=None, client_name: str=None):
        """
        Read raw touches dict from DUT using DUT Name or Client Name
        :param dut_name: name of the DUT. (optional)
        :param client_name: name of the connected dut client. (optional)
        :return:
        """
        client_name = self._dut_name_to_client_name(dut_name) if client_name is None else client_name
        touches = self.dutapi.get_touches(client_name)
        return touches

    def show_image(self, dut, image):
        """
        Show image on DUT screen using
        :param image: image as numpy array, bytes, or filename
        :param dut: Dut Node
        :return: "ok" / error
        """
        dut_name = dut.name
        client_name = self._dut_name_to_client_name(dut_name)
        self.dutapi.show_image(client_name, image)
        return "ok"

    @json_out
    def get_clients(self):
        """
        Read list of connected clients
        :return: list of Dut Communication Client Names, for example ["Client1", "Client2"]
        """
        return self.clients()

    @json_out
    def get_info(self, dut_name: str):
        """
        Get raw info dictionary from connected DUT
        :param dut_name: name of the DUT
        :return: dictionary containing DUT info, like screen pixel size, DUT model.
        """
        return self.info(dut_name)
