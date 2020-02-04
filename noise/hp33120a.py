# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE.chromium file.
from enum import Enum
import glob
import serial
import time


class FunctionGeneratorNotFoundError(IOError):
    pass


class HP33120A(object):
    """ Handles communication with the HP33120A function generator.

    The HP33120A uses standard SCPI serial communication over RS232 8N2.
    Protocol Manual:
    http://sdphca.ucsd.edu/Lab_Equip_Manuals/Agilent_33120a_Users.pdf
    """

    class Waveforms(Enum):
        SQUARE = 'SQU'
        SINE = 'SIN'

    def __init__(self, device_path=None):
        """ Connect to the device either by scanning the ttyUSB* devices or using a
        specifically supplied path.
        """
        possible_paths = [device_path] if device_path else glob.glob('/dev/ttyUSB*')
        self.serial_connection = self._probe_serial_connection(possible_paths)
        if not self.serial_connection:
            raise FunctionGeneratorNotFoundError('Unable to detect function generator!')

    def __del__(self):
        if self.serial_connection:
            self.off()
            self.serial_connection.close()

    def off(self):
        """ Turn off the function generator's output. """
        self._send_message('APPL:DC 1, 1, 0')

    def generate_function(self, form, frequency, amplitude):
        """ Configure the function that the function generator is outputting. """
        if form not in HP33120A.Waveforms:
            raise ValueError('Invalid waveform "%s"!' % form)
        # Put the generator in "remote mode" so it accepts our commands
        self._send_message('SYST:REM')
        # Always set it to Hi-Z mode so we don't accidentally double our voltages.
        # The function generator will otherwise assume there is a 50 Ohm load on the
        # line, and match it internally effectively making a voltage divider of 1/2.
        # Therefore it will compensate by outputting 2x the voltage you expect.
        # In Hi-Z mode this doesn't happen, which is what we want since there is no
        # 50 Ohm load to divide the voltage back down.
        self._send_message('OUTP:LOAD INF')
        # Configure the output function
        cmd = 'APPL:%s %E, %d' % (form.value, int(frequency), int(amplitude))
        self._send_message(cmd)

    def _probe_serial_connection(self, possible_paths):
        """ Find which path in possible_paths points to the serial port that the
        function generator is on.  This is done by opening a serial connection with
        each tty device with the configuration parameters for the HP33120A function
        generator, and probing to determine if it's the correct one.  This
        particular function generator responds with "HEWLETT-PACKARD" when you send
        it "*IDN?" If the device doesn't respond that way, we know we have the wrong
        device.
        This function returns a serial connection object for the correct device, or
        None if no function generator was found.
        """
        for device_path in possible_paths:
            try:
                ser = serial.Serial(
                    port=device_path,
                    baudrate=9600,
                    stopbits=serial.STOPBITS_TWO,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    dsrdtr=True,
                    timeout=1,
                    write_timeout=1
                )
            except serial.serialutil.SerialException:
                continue

            response = None
            try:
                response = self._send_message_aux('*IDN?', ser)
            except serial.serialutil.SerialTimeoutException:
                ser.close()
                continue
            finally:
                if isinstance(response, str) and 'HEWLETT-PACKARD' in response:
                    return ser
                ser.close()
        return None

    def _send_message(self, msg):
        """ Convenience function to automatically send messages to the already
        connected serial port.
        """
        return self._send_message_aux(msg, self.serial_connection)

    def _send_message_aux(self, msg, serial_connection):
        """ Send a message to a function generator at the specified serial
        connection and wait for its response (if there is one).  This function
        either returns the response string or None.
        """
        if not serial_connection:
            raise ValueError("Serial connection to function generator has not been established")
        # Newlines are required to terminate each message
        serial_connection.write(str.encode(msg + '\n', encoding='ASCII'))
        if '?' in msg:
            # The function generator only responds to commands with a '?'  If this
            # message has one, we have to wait for the response and return it.
            response = serial_connection.readline()
            return response.decode()
        return None
