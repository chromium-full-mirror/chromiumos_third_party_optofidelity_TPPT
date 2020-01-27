"""
This is the PST format version of protocol

Handles the lowest level of reading and sending with sockets.


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

import socket
import time

# If timeout is not specified as an argument, this is used.
DEFAULT_TIMEOUT = 0.2

# What string separates length and packet from each other in default protocol
PACKAGE_DELIMITER = '\r'

# If send or recv fails to transfer bytes, this error is raised(IOError).
ERROR_ZERO_BYTES_TRANSFERRED = 'Connection broken.'


class TunnelHandler(object):
    r"""Provides an interface to send and receive packages from socket.
    Reconnecting logic must be handled outside this class.

    Definitions:
        Packet: Contains the actual data.
                 Package is UTF-8 encoded string.
        Package: Contains the actual data (and length of the data).
                 The package format depends from protocol used.

    Protocol:
        Socket stream consists of packages. There is no data between packages.
        E.g. [package1][package2]...[packageN]

        Package contains the necessary information to read one package.
        Therefore it is possible to keep track of the package stream.

    Raises:
        IOError: When recv or send fails with error, this is raised.
                 After raise, new instance of this class must be created,
                 there is no going back. After IOError, if send_data() or
                 get_packet() are called, they should raise IOError again, but
                 there are no guarantees.
                 Note: IOError is not raised when recv timeouts.
        socket.timeout: When recv timeouts, socket.timeout is raised.

    Notes:
        This class does not take unicode as its arguments! Strings must
        be UTF-8 encoded bytestrings.
    """
    def __init__(self, sock, protocol='default'):
        """
        Args:
            sock: Socket object.
        Kwargs:
            protocol: What protocol to use? They are defined in
                      tunnelprotocols.
        """
        self._sock = sock
        self.protocol = protocol

        # When package is read, received bytes are added in
        # this string. If a recv timeouts, we continue from this data.
        self._package = ''

    def close(self):
        """Closes the tunnel."""
        self._sock.close()

    def clear_tunnel(self, timeout=DEFAULT_TIMEOUT):
        """Receive all available data from tunnel and throw it away.

        Kwargs:
            timeout: Timeout in seconds for receiving. Data is received as long
                     as single recv does not timeout.
        """
        self._set_socket_timeout(timeout)
        overall_timeout = 5.0
        start = time.time()

        while True:
            try:
                bytes = self._sock.recv(1024)
                if bytes == '':
                    raise IOError(ERROR_ZERO_BYTES_TRANSFERRED)
            except socket.timeout:
                break
            except socket.error, e:
                raise IOError(e)
            if time.time() - start > overall_timeout:
                break

    def get_packet(self, timeout=DEFAULT_TIMEOUT, crash_on_error=True):
        """Wrapper for _get_packet(). Handles protocol errors.

        Kwargs:
            timeout: See _get_packet().
            crash_on_error: If received data does not follow protocol, should we raise the error or just live with it?
        Returns:
            See _get_packet().
            Addition to that: None is returned if received data does not
            follow the protocol and crash_on_error parameter is False.
        """
        try:
            packet = self._get_packet(timeout=timeout)
        except ValueError:
            if crash_on_error:
                raise
            else:
                packet = None
                self._package = ''  # Reset state.
        return packet

    def send_packet(self, packet, socket_timeout=DEFAULT_TIMEOUT,
                    operation_retries=1):
        """Sends a packet to the socket. I.e. sends package to the socket.
        Shortcut to send [length of the packet in bytes]\r[packet].

        Args:
            packet: str. One packet.
        Kwargs:
            See _send_data()'s docstring.
        """
        length_of_packet = str(len(packet))
        self._send_data(length_of_packet + PACKAGE_DELIMITER + packet,
                        socket_timeout=socket_timeout,
                        operation_retries=operation_retries)

    def _get_packet(self, timeout=DEFAULT_TIMEOUT):
        """Tries to read a packet from tunnel. Continues from last package if
        it was not fully read.

        Kwargs:
            timeout: Timeout in seconds for receiving.

        Returns:
            str. One packet.
        """
        # This means we have not read the length of the packet yet
        if PACKAGE_DELIMITER not in self._package:
            # Continue reading length of the packet
            self._read_until_terminator(PACKAGE_DELIMITER, timeout=timeout)

            # Now self._package contains the whole number and delimiter
            message_length = self._package[:-len(PACKAGE_DELIMITER)]

        # Message length is in the beginning of the packet
        else:
            message_length = self._package.split(PACKAGE_DELIMITER)[0]

        # Every byte after the packet's length and \r in the beginning
        already_read_bytes = self._package.split(PACKAGE_DELIMITER, 1)[1]

        bytes_to_read = int(message_length) - len(already_read_bytes)

        packet = self._read_until_length(bytes_to_read, timeout=timeout)
        packet = already_read_bytes + packet

        # Reset state because this package was successfully read
        self._package = ''
        return packet

    def _read_until_length(self, length, timeout=DEFAULT_TIMEOUT):
        """Read socket until length number of bytes are received, unless
        exception is raised during receiving.

        Args:
            length: length of bytes to read.
        Kwargs:
            timeout: Timeout for receiving in seconds.
        Returns:
            str. length bytes of data from the tunnel.
        """
        self._set_socket_timeout(timeout)

        total_wanted_bytes = length
        received_data = ''
        while len(received_data) < total_wanted_bytes:
            data = self._recv(total_wanted_bytes - len(received_data))
            received_data += data
        return received_data

    def _read_until_terminator(self, terminator, timeout=DEFAULT_TIMEOUT):
        """Read socket until terminator is received, unless
        exception is raised during receiving.

        Args:
            terminator: str. When the last received bytes equals this str
                        receiving is stopped.
        Kwargs:
            timeout: Timeout for receiving in seconds.
        Returns:
            str. All the data before terminator.
        """
        self._set_socket_timeout(timeout)

        received_data = ''
        while not received_data.endswith(terminator):
            data = self._recv(1)
            received_data += data

        # Remove terminator from the end
        received_data = received_data[:-len(terminator)]

        return received_data

    def _recv(self, byte_count):
        """Receives byte_count of bytes at maximum, might receive less.

        Args:
            byte_count: Maximum number of bytes to receive from tunnel.
        Returns:
            str. Data that was received from tunnel.
        """
        try:
            data = self._sock.recv(byte_count)
        except socket.timeout, e:
            raise
        except socket.error, e:
            raise IOError(e)

        # Add received data to package container
        self._package += data
        if data == '':
            raise IOError(ERROR_ZERO_BYTES_TRANSFERRED)
        return data

    def _set_socket_timeout(self, timeout):
        """Sets timeout for socket.

        Args:
            timeout: Timeout in seconds.
        """
        self._sock.settimeout(timeout)

    def _send_data(self, data, socket_timeout=DEFAULT_TIMEOUT,
                   operation_retries=1):
        """Tries to send data to the tunnel with socket_timeout interval. data
        is tried to send operation_retries times. If operation_retries
        decreases to 0 and socket timeouts, IOError is raised.

        Args:
            data: str. Data to be sent to tunnel.
        Kwargs:
            socket_timeout: Timeout for single send attempt.
            operation_retries: Retry count if send timeouts or not all bytes
                               are sent.
        """
        self._set_socket_timeout(socket_timeout)

        bytes_to_send = len(data)
        sent_bytes = 0
        while bytes_to_send > 0:
            try:
                # Send the data that has not been already sent
                sent_bytes = self._sock.send(data[-bytes_to_send:])
                if sent_bytes == 0:
                    raise IOError(ERROR_ZERO_BYTES_TRANSFERRED)
                bytes_to_send -= sent_bytes
            except socket.timeout:
                # If also operation_retries are used, IOError will be raised
                pass
            except socket.error, e:
                raise IOError(e)

            if bytes_to_send > 0 and operation_retries == 0:
                raise IOError("Send operation failed.")

            operation_retries -= 1


# XXXX[packet], length of the XXXX
PACKET_LENGTH_CHAR_COUNT = 4


class PSTTunnelHandler(TunnelHandler):

    def send_packet(self, packet, socket_timeout=DEFAULT_TIMEOUT,
                    operation_retries=1):
        """Sends a packet to the socket. I.e. sends length and data.

        Args:
            packet: str. One packet.
        Kwargs:
            See _send_data()'s docstring.
        """
        # 3 -> 0003, if PACKET_LENGTH_CHAR_COUNT == 4
        length_of_packet = str(len(packet)).zfill(PACKET_LENGTH_CHAR_COUNT)
        self._send_data(length_of_packet + packet,
                        socket_timeout=socket_timeout,
                        operation_retries=operation_retries)

    def _get_packet(self, timeout=DEFAULT_TIMEOUT):
        """Tries to read a packet from tunnel. Continues from last package if
        it was not fully read.

        Kwargs:
            timeout: Timeout in seconds for recveiving.

        Returns:
            str. One packet.
        """
        # This means we have not read the length of the packet yet
        if len(self._package) < PACKET_LENGTH_CHAR_COUNT:
            length_to_read = PACKET_LENGTH_CHAR_COUNT - len(self._package)
            self._read_until_length(length_to_read, timeout=timeout)

            # Now self._package contains the whole number
            message_length = self._package

        # Message length is in the beginning of the packet
        else:
            message_length = self._package[:PACKET_LENGTH_CHAR_COUNT]

        # Every byte after the packet's length in the beginning
        already_read_bytes = self._package[PACKET_LENGTH_CHAR_COUNT:]

        bytes_to_read = int(message_length) - len(already_read_bytes)

        packet = self._read_until_length(bytes_to_read, timeout=timeout)
        packet = already_read_bytes + packet

        # Reset state because this package was successfully read
        self._package = ''
        return packet
