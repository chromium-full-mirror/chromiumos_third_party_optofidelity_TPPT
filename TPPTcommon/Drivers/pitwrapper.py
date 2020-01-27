"""
Wrapper for PIT.

Useful information about dynamic attribute creation:
http://docs.python.org/reference/datamodel.html#customizing-attribute-access


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
import socket
import time

# Own imports
from .clusterizer import Clusterizer

logger = logging.getLogger(__name__)


class PITWrapper(object):
    """Communicates with PIT.

    Note: This class implements magic with attribute lookup. If a non-existing
          attribute is accessed, it will be created dynamically. The new
          created object is callable. Therefore if you call a non-existing
          method in a method which is called from pit_func, it will cause an
          infinite recursive loop.

    You can use PIT's commands just by calling: PITWrapper.Command().
    Accessing a non-existing attribute of PITWrapper, e.g. P2P, will cause
    the __getattr__ method to dynamically create a callable, which sends the
    command and its parameters to PIT, and returns the received data to the
    caller.

    PITWrapper.P2P is callable, which sends command P2P with the same
    parameters that are given to the function.
    E.g. PITWrapper.P2P(1, 2) will send P2P command with parameters 1 and 2 to
    PIT and return the PIT's response to caller.

    That's how normal commands work. They give one response to one request.
    There are also generator commands.
    Generator command produces multiple responses to one request.
    They are explicitly defined in self.generator_commands dict.
    If a non-existing attribute is accessed that happens to be a generator
    command, a generator is returned instead of callable function.
    The returned generator will yield return values from PIT as long as the
    condition function returns True. Condition function is also defined in the
    self.generator_commands dict.
    """

    def __init__(self, tunnel=None, host=None, port=None, target=2, sender=4):
        """
        This class supports two types of constructing. Either with already
        initialized tunnel, or with host/port combination.

        Kwargs:
            tunnel: Handler to tunnelhandler.
            host: PIT's ip address.
            port: PIT's port.
            target: Target's id. Used to determine which module sent the
                    packet.
            sender: Sender's id.
        """
        self._tunnel = tunnel

        if self._tunnel is None:
            if host is None or port is None:
                raise NameError("Host and port are not defined!")

            from .tunnelhandler import TunnelHandler

            self.pit_ip_address = host
            self.pit_port = port

            # Initialize tunnel, tunnel handles the protocol between PIT
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.connect((self.pit_ip_address, self.pit_port))
            self._tunnel = TunnelHandler(self._sock)
        else:
            if host is not None or port is not None:
                raise NameError("Use only one type of constructing.")

        self.target = target
        self.sender = sender

        # If for some reason PIT is still sending data to socket.
        # Just a precaution.
        self._tunnel.clear_tunnel()

        # Commands that causes PIT to send continuous data back until a
        # condition changes.
        # Format: {Casesensitive_name: callable}
        # The packets are received as long as the callable returns True
        # Callable should have one parameter, which is the packet received
        # from PIT.
        self.generator_commands = {'CLine': self._cline_check}

    def __getattr__(self, name):
        """If class' attribute is accessed and it does not exist, this
        method will be called.

        Returns:
            A function that will call PIT's function named name.
        """
        def pit_func(*args):
            # Python gives arguments as a tuple, convert them to list.
            gen = self._send_command(name, list(args))

            if name in self.generator_commands:
                # Return the actual generator.
                return gen
            else:
                # Return the first item of the generator.
                return gen.next()
        return pit_func

    def close(self):
        """Closes the tunnel."""
        self._tunnel.close()

    def _cline_check(self, xml_data):
        """Returns False, when CLine should be stopped."""
        cluster = Clusterizer(xml_data)
        if cluster.Command == 'Error':
            return False
        return True

    def _parse_return_data(self, xml_data):
        """Parses return data from the XML format that PIT outputs.

        Args:
            xml_data: str. XML format string that was received from PIT.
        Returns:
            Returns pythonic return values.
        """
        cluster = Clusterizer(xml_data)
        # Data is in format: [str_repr_of_obj]. E.g. ['(1, 2)'] or ['2']
        return_data = cluster.Data[0]

        if cluster.Command == 'Error':
            raise Exception(return_data)

        # If nothing is returned the return_data is '', make it more pythonic
        # by returning None
        if len(return_data) == 0:
            return None

        try:
            # Otherwise we have to cast the str to actual object
            return_data = eval(return_data)
        except SyntaxError:
            # Casting failed, so it is a str.
            pass
        return return_data

    def _get_return_value(self, command, timeout=None):
        """Gets response from tunnel and returns it.

        Args:
            timeout: Timeout for receiving.
        """
        max_wait_time = 5
        start = time.time()
        while True:
            xml_data = self._tunnel.get_packet(timeout=timeout)
            cluster = Clusterizer(xml_data)
            if cluster.Command == command:
                return_value = self._parse_return_data(xml_data)
                return return_value
            if time.time() - start > max_wait_time:
                raise Exception("Timeout while waiting response to PIT command %s" % command)

    def _send_command(self, command, parameters):
        """Sends command to PIT.

        Args:
            command: PIT command.
            parameters: Parameters to command.
        Returns:
            A generator which yields responses from PIT.
            If command is not a generator command, this will yield only one
            response. Otherwise values are yielded until condition_func
            returns False.
        """
        # Format the XML data to be sent.
        signal = Clusterizer()
        signal.Command = command
        signal.Data = parameters
        signal.Target = self.target
        signal.Sender = self.sender
        signal.ID = time.time()

        logger.debug('Send command: %s' % command)
        self._tunnel.send_packet(signal.tostring())
        
        if command in self.generator_commands:
            # Receive and yield packets until the condition_func returns False.
            while True:
                xml_data = self._tunnel.get_packet(timeout=None)

                condition_func = self.generator_commands[command]
                if not condition_func(xml_data):
                    # The last packet which ends the packet "stream", will not
                    # be yielded.
                    break

                cluster = Clusterizer(xml_data)
                if cluster.Command == command:
                    return_value = self._parse_return_data(xml_data)
                    yield return_value
        else:
            yield self._get_return_value(command)
