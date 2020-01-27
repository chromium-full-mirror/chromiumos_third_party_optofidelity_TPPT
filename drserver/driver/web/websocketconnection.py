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

import websocket_server
import threading
import json
import typing
import logging


log = logging.getLogger(__name__)


"""
Websocket connection to multiple clients.
Usage:
    # open server at port 50000
    # every second send command "hello" with parameters to every connected client and print result.
    WebsocketConnection.start_server(50000)
    while True:
        for client in WebsocketConnection.clients():
            response = client.command("hello", {"variable": 1})
            print(response) 
            time.sleep(1)
            
client.command will send one string to the client:
    command name separated with space from json-encoded parameters + newline \n. 
    "command json-parameters<newline>"
    - Parameters cannot have any data that breaks the json formatting or newline at the end.
    - If you need free form data transmitted, use base64-encoding.
    The return value from client will be json-formatted response.

"""


class WebsocketConnectionObserver:
    """
    Virtual observer class for following client connections.
    If you are interested in connecting / disconnecting clients, derive your interface class from this class.
    """
    def client_connected(self, client: "WebsocketConnection"):
        raise NotImplementedError()

    def client_disconnected(self, client: "WebsocketConnection"):
        raise NotImplementedError()


class WebsocketConnection:
    __clients = {}
    __server = None
    __observers = []
    __client_counter = 0

    def __init__(self, handler):
        self.handler = handler
        self.condition = threading.Condition()
        self.response = None
        self._send_and_receive_lock = threading.Lock()

        WebsocketConnection.__client_counter += 1
        self.client_id = "client_{}".format(WebsocketConnection.__client_counter)

        WebsocketConnection.__clients[self.client_id] = self
        log.info("New websocket client. number of clients: {}".format(len(WebsocketConnection.__clients)))

    @classmethod
    def add_observer(cls, observer: WebsocketConnectionObserver):
        """
        Adds an observer for events where new client is connected or existing client has closed the connection.
        :param observer: Instance of WebSocketConnectionObserver class.
        """
        cls.__observers.append(observer)

    @classmethod
    def remove_observer(cls, observer: WebsocketConnectionObserver):
        """
        Removes previously registered observer.
        :param observer: Instance of WebSocketConnectionObserver class.
        """
        i = cls.__observers.index(observer)
        del cls.__observers[i]

    @staticmethod
    def start_server(host: str, port: int):
        def start_server():
            server = websocket_server.WebsocketServer(host=host, port=port)
            server.set_fn_message_received(WebsocketConnection.message_received)
            server.set_fn_new_client(WebsocketConnection.new)
            server.set_fn_client_left(WebsocketConnection.close)
            WebsocketConnection.__server = server
            server.serve_forever()

        log.info("starting http server at port {}".format(port))
        t = threading.Thread(target=start_server, daemon=True)
        t.start()

    @classmethod
    def new(cls, params: dict, _) -> 'WebsocketConnection':
        handler = params["handler"]
        new_connection = WebsocketConnection(handler)
        for observer in cls.__observers:
            observer.client_connected(new_connection)
        return new_connection

    @classmethod
    def clients(cls):
        return cls.__clients

    @classmethod
    def message_received(cls, params, _, message):
        handler = params["handler"]
        client = cls.client_of_handler(handler)
        with client.condition:
            client.response = message
            client.condition.notify()

    @classmethod
    def client_of_handler(cls, handler) -> [typing.Optional, 'WebsocketConnection']:
        for client_id in cls.__clients:
            client = cls.__clients[client_id]
            if client.handler == handler:
                return client
        return None

    @classmethod
    def close(cls, params: dict, _: websocket_server.WebsocketServer):
        client = cls.client_of_handler(params["handler"])

        for observer in cls.__observers:
            observer.client_disconnected(client)

        with client.condition:
            client.response = "error {}".format("closed")
            client.condition.notify()

        del cls.__clients[client.client_id]
        log.info("Websocket closed. number of clients: {}".format(len(WebsocketConnection.__clients)))

    def _send_and_receive(self, msg: str):
        try:
            with self._send_and_receive_lock:
                self.handler.send_text(msg)
                with self.condition:
                    self.condition.wait()
                    response = self.response
                    self.response = None

            return response

        except Exception as e:
            log.error("Error in websocket send_and_receive : {}".format(e))
            return "error {}".format(e)

    def command(self, command: str, params=None):
        msg = command

        if params:
            msg += " " + json.dumps(params)

        msg += "\n"

        r = self._send_and_receive(msg)
        if not r.startswith("ok"):
            raise Exception("send and receive not ok : {}".format(r))
        r = json.loads(r[3:])  # remove 'ok '
        return r

if __name__ == '''__main__''':
    def __test():
        import time

        WebsocketConnection.start_server("0.0.0.0", 50010)
        while True:
            for client_name in WebsocketConnection.clients():
                client = WebsocketConnection.clients()[client_name]
                response = client.command("get_info")
                print(response)
                time.sleep(1)
    __test()
