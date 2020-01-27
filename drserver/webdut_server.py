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
from . import driver
import numpy as np
import socket
import threading
import time


import logging
log = logging.getLogger(__name__)


"""
Server for websocket-based clients.
- Webpage client
- Chrome extension client

Example settings:

- name: dutserver
  cls: WebDutServer
  parent: tnt
  arguments:
    host: 0.0.0.0
    port: 50008
  connection: tnt

"""

class ClassicDutApi:
    """
    Web client cannot connect to any normal socket.
    Web client uses websockets instead.
    = Web client cannot act as a Classic TnT Client by itself.

    This class imitates the Classic TnT Client
    - Connects to 127.0.0.1:50007 (supposedly TnT Sequencer has port open)
    - Polls touches from every connected client
    - Sends all touches in Classic TnT Client api format to TnT Sequencer through socket.
    """

    def __init__(self, dutapi: driver.web.chrome_extension_client.ChromeExtensionClientInterface, host: str, port: int):
        self.socket = socket.socket()
        self.dutapi = dutapi
        self._running = False
        self._thread = None
        self._host = host
        self._port = port

    def start(self):
        if self._running:
            return

        print("classic dut api start")

        self._thread = threading.Thread(target=self.loop, daemon=True)
        self._running = True
        self._thread.start()

    def stop(self):
        if not self._running:
            return

        print("classic dut api stop")

        self._running = False
        self._thread.join()
        self._thread = None

    def loop(self):
        print("classic dut api loop start ")

        while self._running:
            try:
                log.info("WebDutServer classic api connecting to sequencer at {} {}".format(self._host, self._port))
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((self._host, self._port))
                print("WebDutServer classic api connected to sequencer at {} {}".format(self._host, self._port))
                break
            except Exception as e:
                print("WebDutServer classic api could not connect to sequencer: {}".format(e))
                time.sleep(1)

        time_interval = 1.0  # poll interval seconds.

        def convert_touches(touches):
            fields = touches["fields"]
            touches = touches["touches"]
            x_index = fields.index("x")
            y_index = fields.index("y")
            t_index = fields.index("time")
            a_index = fields.index("action")
            i_index = fields.index("id")

            r = []

            pressure, orientation, tilt, distance = 0, 0, 0, 0

            for t in touches:
                r.append((t[x_index], t[y_index], pressure, t[i_index], 0, t[t_index], t[a_index], orientation, tilt,
                          distance))
            return r

        while self._running:

            client_names = self.dutapi.clients
            for client_name in client_names:
                client = self.dutapi.clients[client_name]
                touches = client.command("touches")
                touches = convert_touches(touches)
                if len(touches):
                    msg = "["
                    for t in touches:
                        msg += "{}, ".format(t)
                    #for action, x, y, timestamp, identifier in touches:
                    #    msg += "({},{},{},{},0,{},{},{},{},{}), ".format(x, y, pressure, identifier,
                    #                                                     timestamp, action, orientation, tilt, distance)
                    msg = msg[:-1]  # remove last space
                    msg = msg + "'OK','']"

                    header = str(len(msg))
                    header = "0000"[len(header):] + header

                    msg = header + msg

                    sock.sendall(msg.encode("ascii"))

            time.sleep(time_interval)

        print("classic dut api loop end")


class WebDutServer(Node):
    """
    Dut communication server
    """
    static = None

    class DutNotFoundError(Exception):
        pass

    def __init__(self, name):
        super().__init__(name)
        WebDutServer.static = self

    def _init(self, **kwargs):
        """
        Classic server port has been 50007
        New protocol port should be classic+1, thus here 50008
        :param kwargs:
        :return:
        """
        host = kwargs.get("host", "0.0.0.0")
        port = int(kwargs.get("port", 50008))
        self.dutapi = driver.web.ChromeExtensionClientInterface(host, port, self)
        self.classic_api = ClassicDutApi(self.dutapi, "127.0.0.1", 50007)

    def clients_changed(self):
        if len(self.clients()):
            self.classic_api.start()
        else:
            self.classic_api.stop()

    def _dut_name_to_client_name(self, dut_name: str):
        """
        Map TnT Dut Name to Dut communication client name
        for example "Dut1" -> "Client1"
        All the communication with physical DUT is done using Client Name
        :return: mapped client name
        """
        client_names = [name for name in self.dutapi.clients]
        for client_name in client_names:
            info = self.info(client_name=client_name)
            name = info.get("dut_name", None)
            if name is not None and name == dut_name:
                return client_name
        raise WebDutServer.DutNotFoundError("communication client not found for dut name {}".format(dut_name))

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
        except WebDutServer.DutNotFoundError:
            return False
        return client_name in self.clients()

    def info(self, dut_name: str = None, client_name: str = None):
        """
        Read raw info dict from DUT using DUT Name or Client Name
        :param dut_name: name of the DUT. (optional)
        :param client_name: name of the connected dut client. (optional)
        :return:
        """
        client_name = self._dut_name_to_client_name(dut_name) if client_name is None else client_name
        info = self.dutapi.get_info(client_name)
        return info

    def touches(self, dut_name: str = None, client_name: str = None):
        """
        Read touches from the connected DUT using either Dut Name or Client Name
        :param dut_name: name of the DUT (optional)
        :param client_name: name of the connected Client (optional)
        :return: dictionary containing all the touches since las 'touches' call, for example:
                 {
                 "touch_fields", ["x", "y", "force"],
                 "touches", [[10, 10, 1], [100, 10, 1], [100, 100, 1]]
                 }
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
        if image is None:
            image = np.zeros((10, 10, 3), dtype=np.uint8)
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

    @json_out
    def get_touches(self, dut_name: str):
        """
        Read touches from connected DUT
        Reading will clear current list of touches from the device.
        :param dut_name: name of the DUT
        :return: dictionary containing touch fields and touches, for example:
                 {
                 "touch_fields", ["x", "y", "force"],
                 "touches", [[10, 10, 1], [100, 10, 1], [100, 100, 1]]
                 }

        """
        touches = self.touches(dut_name)
        fields = ["action", "x", "y", "timestamp", "finger_id"]
        return {"touches": touches, "touch_fields": fields}
