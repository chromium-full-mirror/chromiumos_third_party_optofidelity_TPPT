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
import cv2
import numpy as np
import socket
from threading import Thread
import queue
import time
import json
from collections import OrderedDict
import logging

log = logging.getLogger(__name__)


class DutCommunicationClient:
    """
    Instance of one DUT client
    """
    def __init__(self, name, sock: socket):
        self.name = name
        self.socket = sock
        self.info = None


class DutCommunication:
    """
    DUT communication client or server (start_server / start_client)
    - low level layer
    - packet send / receive only

    Create high level protocols on top of this server
    """

    client_counter = 0

    def __init__(self, auth_key=None):
        self.queue = None
        self.socket = None
        self._clients = OrderedDict()
        self._connect_thread = None
        self._terminate = False
        self._rcv_buffer = bytearray()
        self.auth_key = auth_key

    def __exit__(self, exc_type, exc_val, exc_tb):
        # try cleanup sockets when closing
        self.close()

    def close(self):
        """
        Close the server
        """
        self._terminate = True
        if self._connect_thread is not None:
            self._connect_thread.join()

    def start_server(self, host: str, port: int):
        """
        Start communication as server
        - listen for incoming connections from clients

        :param host: server host address
        :param port: server port
        """
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind the socket to the port
        server_address = (host, port)
        log.info('starting listening client connections at address {} port {}'.format(host, port))

        # try binding the socket until success
        while True:
            try:
                sock.bind(server_address)
                break
            except Exception as e:
                log.warning("could not bind server socket, retrying ({})".format(e))
                time.sleep(1)

        # Listen for incoming connections
        sock.listen(1)

        self.socket = sock

        # create thread and communicating queue, start thread
        self.queue = queue.Queue()

        t = Thread(target=self._connection_thread)
        self._connect_thread = t
        t.start()

    def start_client(self, host: str, port: int):
        """
        Starts communication as client

        :param host: server host
        :param port: server port
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        self.socket = s

    def authenticate_dut(self, client):
        if self.auth_key == None:
            return False
        try:

            # Send the has to DUT
            command = 'AUTH'
            pkt = self.create_packet(command, bytes(self.auth_key, 'utf-8'))
            _, reply_bytes = self._send_and_receive(client, pkt)
            reply = reply_bytes.decode('utf-8')

            # Check the reply
            if reply == 'OK':
                return True
            else:
                return False

        except Exception as e:
            log.error("Error in DUT authentication: " + str(e))
            return False

    def _connection_thread(self):
        self.socket.setblocking(0)
        while self._terminate == False:
            # Wait for a connection
            # print('DUT communication server waiting for a connection')
            try:
                connection, client_address = self.socket.accept()
            except:
                connection = None

            if connection is not None:
                connection.setblocking(1)
                DutCommunication.client_counter += 1
                name = "client{}".format(DutCommunication.client_counter)
                client = DutCommunicationClient(name, connection)
                # Authenticating client, if it is succesful client is added if not it is removed
                if self.authenticate_dut(client):
                    log.info("DUT communication server has a new connection with name {}".format(name))
                    self.queue.put(client, block=False)
                else:
                    self._remove_client(client)
                    DutCommunication.client_counter -= 1
                    log.info("DUT authentication failed with {}".format(name))
            time.sleep(1)
        print("end of connection thread")

    @staticmethod
    def create_packet(cmd: str, data=None):
        """
        Create data packet
        :param cmd: command as 4-chr string, like "SIMG" ( show image )
        :param data: data as bytes
        :return: packet as bytes
        """
        # cmd must be at least 4 characters, shorter are padded with space
        cmd = cmd + "    "[:4 - len(cmd)]
        # cmd must be exactly 4 characters
        cmd = cmd[:4]
        cmd = cmd.encode("ascii")

        if data is None:
            data = bytearray()

        data_len = len(data).to_bytes(4, "little")
        header = "OTGP".encode("ascii")

        pkt = header + cmd + data_len + data
        return pkt

    @staticmethod
    def parse_packet(data):
        """
        Parses data packet
        :param data: data as bytes
        :return: None or (header, command, data, remainder (if any))
        """
        # data must contain at least 12 bytes to read the header
        header_length = 12
        if len(data) < header_length:
            return None

        header = data[0:4].decode("ascii")
        command = data[4:8].decode("ascii")
        data_length = int.from_bytes(data[8:12], "little")

        if len(data) - header_length < data_length:
            return None

        data = data[header_length: header_length + data_length]
        remainder = data[header_length + data_length:]

        return header, command, data, remainder

    def send_and_receive(self, client: DutCommunicationClient, cmd: str, data=None):
        """
        Server uses this function for all communication
        All communication starts from server and is responded by client
        Any error (socket closed, timeout) will result in removing the connection from list and raising exception
        :param client_name: client name
        :param cmd: command name, 4 chars
        :param data: data to send, bytearray / bytes
        :return: received packet
        """
        if client.name not in self.clients:
            raise Exception("No such client")
        pkt = self.create_packet(cmd, data)
        rv = self._send_and_receive(client, pkt)
        return rv

    def receive_and_respond(self, command_handle_function):
        """
        Client uses this function for all communication
        All communication starts from server and is responded by client
        Will stay in function until rcv-respond is done, or exception occured
        Any error will result in exception

        :param command_handle_function function that handles actual command
        """

        # 1. read data until complete packet can be parsed
        # 2. handle command with given command_handle_function
        # 3. respond with return value from command_handle_function

        self.socket.setblocking(0)
        while True:
            try:
                self._rcv_buffer += self.socket.recv(16384)
            except BlockingIOError:
                break

            except Exception as e:
                raise Exception("Connection closed")

            read_packet = self.parse_packet(self._rcv_buffer)
            if read_packet is not None:
                header, command, data, remainder = read_packet
                self._rcv_buffer = remainder

                command, data = command_handle_function(command, data)
                packet = self.create_packet(command, data)
                self.socket.sendall(packet)
                break


    def _rcv_packet(self, client: DutCommunicationClient, timeout):
        """
        Receives a packet from client
        :param client: client to receive packet from
        :param timeout: timeout in seconds after which an exception is raised
        :return: received packet
        """

        t0 = time.time()
        while time.time() < t0 + timeout:
            try:
                self._rcv_buffer += client.socket.recv(16384)
            except Exception as e:
                self._remove_client(client)
                raise e
            read_packet = self.parse_packet(self._rcv_buffer)
            if read_packet is not None:
                header, command, data, remainder = read_packet
                self._rcv_buffer = remainder
                return command, data

        self._remove_client(client)
        raise Exception("Reading result timed out")

    def _send_and_receive(self, client: DutCommunicationClient, packet, timeout=1):
        """
        Any error (socket closed, timeout) will result in removing the connection from list and raising exception
        :param client: client to send to
        :param packet: packet to send
        :param timeout: timeout in seconds (after which exception)
        :return: the return packet from the client
        """
        try:
            client.socket.sendall(packet)
        except Exception as e:
            self._remove_client(client)
            raise e

        packet = self._rcv_packet(client, timeout)
        return packet

    def _remove_client(self, client):
        try:
            client.socket.close()
        except Exception:
            pass

        try:
            del self._clients[client.name]
        except Exception:
            pass

    @property
    def clients(self):
        while not self.queue.empty():
            new_client = self.queue.get(block=False)
            self._clients[new_client.name] = new_client
        return self._clients



class DutAPI:
    """
    High level DUT API

    easy-to-use dut communication server
    open the server with host and port (127.0.0.1, 50008 for example)
    wait for a client to connect
    - list clients
    - get info from a client
    - show image on client screen
    """
    def __init__(self, host: str, port: int, auth_key = None):
        self.__comm = DutCommunication(auth_key)
        self.__comm.start_server(host, port)

    def close(self):
        """
        Close the communication server
        """
        self.__comm.close()

    def show_image(self, client: str, image):
        """
        show image on client screen
        :param client: name of the client
        :param image: image as str (filename), numpy array image or bytearray of jpg/gif/png.
                        If image is None, the screen will be emptied
        :return: response packet from client
        """
        if issubclass(image.__class__, str):
            with open(image, "rb") as file:
                data = file.read()

        elif issubclass(image.__class__, np.ndarray):
            _, data = cv2.imencode(".png", image)
            data = data.tobytes()

        elif issubclass(image.__class__, bytes):
            data = image

        elif image is None:
            data = bytearray() # empties the screen

        else:
            raise Exception("Unknown image input")

        client = self.__comm.clients[client]
        rcv_packet = self.__comm.send_and_receive(client, "SIMG", data)
        return rcv_packet

    def get_info(self, client: str):
        """
        reads dut information.
        Usually has information about the device, screen size, etc.
        :param client: name of the client
        :return: info as dictionary
        """
        client = self.__comm.clients[client]
        if client.info is None:
            command, data = self.__comm.send_and_receive(client, "GINF")
            client.info = json.loads(data.decode("utf-8"))
        return client.info

    def get_touches(self, client: str):
        """
        Reads dut touches.
        :param client: name of the client
        :return: info as dictionary
        """
        client = self.__comm.clients[client]
        command, data = self.__comm.send_and_receive(client, "GTCH")
        touches = json.loads(data.decode("utf-8"))
        return touches

    @property
    def clients(self):
        """
        get list of currently connected clients
        :return: list of clients
        """
        return self.__comm.clients

