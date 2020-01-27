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

from .websocketconnection import WebsocketConnection, WebsocketConnectionObserver
import cv2
import numpy as np
import base64


class ChromeExtensionClientInterface(WebsocketConnectionObserver):
    def __init__(self, host: str, port: int, observer):
        """
        Initializes the client interface.
        :param host: tcp/ip host, usually "0.0.0.0"
        :param port: tcp/ip port
        """
        WebsocketConnection.start_server(host, port)
        WebsocketConnection.add_observer(self)
        self._observer = observer

    def client_connected(self, client: WebsocketConnection):
        self._observer.clients_changed()

    def client_disconnected(self, client: WebsocketConnection):
        self._observer.clients_changed()

    @property
    def clients(self) -> list:
        """
        :return: List of client names.
        """
        clients = WebsocketConnection.clients()
        return clients

    @classmethod
    def get_info(cls, client_id: str) -> dict:
        """
        Gets info dictionary of DUT.
        :param client_id: ID of the client.
        :return: (dict) DUT info.
        """
        client = WebsocketConnection.clients()[client_id]
        response = client.command("get_info")
        return response

    @classmethod
    def show_image(cls, client_id: str, image: np.ndarray):
        """
        Shows numpy array image on DUT display.
        :param client_id: ID of the client.
        :param image: Image as numpy array.
        """
        client = WebsocketConnection.clients()[client_id]
        _, image_png = cv2.imencode(".png", image)
        image_data_b64 = base64.b64encode(image_png.tobytes()).decode("ascii")
        client.command("draw_image", {"image": image_data_b64})

    @classmethod
    def get_touches(cls, client_id: str):
        """
        Get touch info from the DUT.
        :param client_id: ID of the client.
        :return:
        """
        client = WebsocketConnection.clients()[client_id]
        return client.command("touches")
