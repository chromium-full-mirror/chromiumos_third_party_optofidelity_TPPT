"""
DeviceSocket is the connection between a script and device under test.
DeviceSocket is basically the same as TCPSocket module in PST.


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

import logging
import json
import queue
import select
import socket
import threading
import os
import os.path
import time

from collections import namedtuple, UserList
from optofidelity_protocols.dut import Axis, DUTConfig

log = logging.getLogger(__name__)

PORT = 50007


class ClientList(UserList):
    def sockets(self):
        """ :return: list of all Clients' corresponding sockets. """
        return [c.sock for c in self.data]

    def remove_socket(self, sock):
        """ Remove Clients with the given socket. """
        self.data = [c for c in self.data if sock is not c.sock]

    def set_config(self, sock, config):
        """ Set the config of Clients with the given socket. """
        for client in self.data:
            if sock is client.sock:
                client.set_config(config)

    def get_by_client_id(self, client_id):
        """ :return: list of Clients with matching client_id. """
        return [c for c in self.data if client_id == c.client_id]


class Client(object):
    def __init__(self, sock):
        self.sock = sock
        self.config = None

    @property
    def client_id(self):
        """ :return: The client_id, if the config has been set """
        if self.config is not None:
            return self.config.client_id
        return None

    def request_config(self):
        """ Send request to client for config """
        self.sock.send("CONFIG".encode("utf-8"))

    def set_config(self, config):
        """ Set the config for this Client

        :param config: A list containing the config, matching the DUTConfig namedtuple layout,
        where the first item is the client_id and the remaining items are lists matching
        the Axis namedtuple.
        """
        for i in range(1, len(config)):
            config[i] = Axis(*config[i])
        self.config = DUTConfig(*config)


class DeviceSocket(threading.Thread):    

    def __init__(self):
        self.clients = ClientList()
        self.queue = queue.Queue()
        self.server_thread = threading.Thread(target=self.server, args =(self.queue,))
        self.server_thread.start()

    def server(self, queue):
                # List to keep track of socket descriptors

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # this has no effect, why ?
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", PORT))
        self.server_socket.listen(10)

        input = ""

        while True:
            # Get the list sockets which are ready to be read through select
            connection_list = self.clients.sockets()
            connection_list.append(self.server_socket)
            read_sockets, _, _ = select.select(connection_list, [], [])

            for sock in read_sockets:
                #New connection
                if sock == self.server_socket:
                    # Handle the case in which there is a new connection received through server_socket
                    sockfd, addr = self.server_socket.accept()
                    client = Client(sockfd)
                    client.request_config()
                    self.clients.append(client)

                    log.debug("Client ({}, {}) connected".format(addr[0], addr[1]))

                    #self.broadcast_data(sockfd, "[%s:%s] entered room\n" % addr)
                 
                #Some incoming message from a client
                else:
                    # Data recieved from client, process it
                    try:
                        #In Windows, sometimes when a TCP program closes abruptly,
                        # a "Connection reset by peer" exception will be thrown
                        
                        # input must have at least '4' characters
                        while len(input) < 4:
                            input += sock.recv(4).decode("utf-8")
                            # Test that client is still connected to avoid forever loop; if recv returns 0, the client has disconnected
                            if len(input) == 0:
                                break
                        length = int(input[:4])
                        input = input[4:]

                        # input must have at least 'length' characters
                        while len(input) < length:
                            input += sock.recv(length).decode("utf-8")

                        # store extra characters if any, cut input to length
                        restInput = input[length:]
                        input = input[:length]
                            
                        if input.startswith("CHAL "):
                            log.debug("Authenticating Device: {}".format(str(sock.getpeername())))
                            resp = self.authenticate(input[5:])
                            response = "RESP " + resp
                            sock.send("0021".encode("utf-8"))
                            sock.send(response.encode("utf-8"))
                        elif input.startswith("CONFIG "):
                            config = json.loads(input[7:])
                            self.clients.set_config(sock, config)
                        else:
                            results = json.loads(input)
                            #log.debug("Put touch event to queue: {}".format(results))
                            queue.put(results)

                         # put the rest of the characters back to input
                        input = restInput
                        
                    except Exception as e:
                        log.info(e)
                        #self.broadcast_data(sock, "Client (%s, %s) is offline" % addr)
                        log.debug("Client ({}, {}) is offline".format(addr[0], addr[1]))
                        sock.close()
                        self.clients.remove_socket(sock)
                        continue

        server_socket.close()

    def get_config_by_client_id(self, client_id):
        """ Get the configuration associated with the Client with the given client_id.

        Raise a ValueError if there are no matches, or multiple matches.
        """
        matches = self.clients.get_by_client_id(client_id)
        if len(matches) == 0:
            raise ValueError("No DUT found with client ID %d" % client_id)
        if len(matches) > 1:
            raise ValueError("%d DUTs found with client ID %d. Try again after disconnecting DUTs with duplicate "
                             "client IDs" % (len(matches), client_id))
        return matches[0].config

    def close_server(self):
        self.server_thread.join()

    def broadcast_data(self,sock, message):
        # Do not send the message to the main socket or the client who has sent us the message.
        for client in self.clients:
            if client.sock != sock :
                try :
                    client.sock.send(message.encode("utf-8"))
                except :
                    # broken socket connection may be, chat client pressed ctrl+c for example
                    client.sock.close()
                    self.clients.remove(client)

    def handle_queue(self):
            while not self.queue.empty():
                result = self.queue.get()
                self.queue.task_done()
                log.debug(result)
    def clear_queue(self):
        while not self.queue.empty():
            self.queue.get()
            self.queue.task_done()
    def ReturnP2PArray(self, timeout = 2.0):
        try:
            retval = self.queue.get(timeout=timeout)
            self.queue.task_done()
            return retval
        except:
            return []
    def CLine(self, timeout = 2.0):
        while True:
            item = self.queue.get(timeout=timeout)
            self.queue.task_done()
            if item is None:
                break
            yield item

    def authenticate(self, challenge):
        '''Performs HASP authentication when requested by the
        program running on the device.'''
        exepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "authenticate.exe")#"../engine/authenticate.exe")
        response = os.popen(exepath + " " + challenge).read().strip()
        return response

    def update_line(self,x_array, y_array, hl):
        hl.set_ydata(y_array)
        hl.set_xdata(x_array)
        plt.draw()
    
    def print_touch_data(self,input_results,draw_touches, hl):
        results = input_results
        touchlist = []
        
        if len(results) > 0:
            if "OK" in results:
                for point in range(results.index("OK")):  # Read all data points before "OK"
                    touchlist.append([results[point][0], results[point][1], results[point][2],
                                      results[point][3], results[point][4], results[point][5], results[point][6]])
            x_array = []
            y_array = []
            for touch in touchlist:
                
                event = int(touch[6])
                if event == 0:
                    event_name = "MOVE_DOWN"
                elif event == 1:
                    event_name = "MOVE_UP  "
                elif event == 2:
                    event_name = "ACTION_MOVE"
                elif event == 9:
                    event_name = "HOVER_DOWN "
                elif event == 10:
                    event_name = "HOVER_UP  "
                elif event == 7:
                    event_name = "HOVER_MOVE"
                else:
                    event_name = "Unknown event: " + str(event)
                log.debug("IP: " + str(sock.getpeername()[0]) +"\tEvent: "+ event_name + "\tPressure: " + str(touch[2]) +"\tX: " + str(touch[0]) + "\t Y: " + str(touch[1])+ "\t Finger: " + str(touch[3])+ "\t Timestamp: " + str(touch[5]))
                if draw_touches:
                    x_array.append(touch[0])
                    y_array.append(touch[1])
            if draw_touches:    
                self.update_line(x_array,y_array, hl)
