"""
A driver program that communicates with PIT HW component and channelize the
commands to test DUTs (e.g. touch panels) on the table


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
import time
#from math import *

# Interfacing guide:
# http://www.synaptics.com/sites/default/files/511-000136-01-Rev-E-RMI4-Interfacing-Guide.pdf

# I2C driver:
# https://files/svn/design/design/OF_PIT/docs/manufacturing/InstallationFiles/python/i2c_driver.py

# "constants" for looking function's registers from dict
QUERY = 'query'
CONTROL = 'control'
DATA = 'data'
COMMAND = 'command'

# status errors for initialize
status_errors = {0x01: 'Reset Occured.', 0x02: 'Invalid Configuration.',
                 0x03: 'Device Failure.', 0x04: 'Configuration CRC Failure',
                 0x05: 'Firmware CRC Failure.', 0x06: 'CRC In Progress.'}

#==================== List of variables ====================================#
# Speed value used with i2c
speed_value = 100
# delay value assigned for p2p connection (in ms)
p2p_delay_value = 8000
# delay value assigned for cline connection (in ms)
cline_delay_value = 3000

class device_driver:
    """Synaptic driver demo"""

    def __init__(self, i2c):

        # init i2c communication
        self.i2c = i2c
        self.i2c.setspeed(speed_value)

        self._p2p_delay = 0
        self._cline_delay = 0
        self._2d_version = 0x11
        self._address = 0x4B
        self._pdt_top_address = 0xEF  # pdt = Page Description Table
        self._function_descriptions_address = self._pdt_top_address - 1
        self._functions = {}
        self._current_page = 0
        self._supported_fingers = 0
        self._F11_2D_Data0_register_count = 0

    def Initialize(self, Setup=0):
        """ Inits the device """

        # find device address
        self._address = self.find_device_address()
        self.i2c.read_ext_rise_fall([1, 0, 1, 1, 1, 1, 1, 1])

        if self._address is False:
            raise Exception('Initializing error:', 'Device not found.')

        # get functions from Page Description Table and add them to a dict
        self.get_and_add_functions()

        # check 2D sensing version, defaults to 0x11
        if 0x12 in self._functions:
            self._2d_version = 0x12

        F11_2D_info = self.read_register(QUERY, self._2d_version, 0, 6)

        # get amount of supported fingers
        # bits 2:0 (3-bit field) at F11_2D_Query1
        fingers = F11_2D_info[1] & 0x07

        if fingers < 5:
            self._supported_fingers = fingers + 1
        else:
            self._supported_fingers = 10

        # F11_2D_Data0 register block size formula:
        # F11_2D_Data0_registerCount = ceil(NumberOfFingers/4)
        # formula can be found from interfacing guide
        self._F11_2D_Data0_register_count = \
                                        int(ceil(self._supported_fingers / 4.0))

        # get device status
        status_info = self.read_status_registers()
        status_code = status_info[0] & 0x0F

        # check status
        # panel gives always "0x01: 'Reset Occured.'" if it hasn't reseted
        if status_code == 0x00 or status_code == 0x01:
            pass  # No Error.
        else:
            if status_code in status_errors:
                raise Exception('Initializing error:',
                                status_errors[status_code])
            else:
                raise Exception('Initializing error:',
                                'Unknown error occured.')

        if Setup == 0:
            self._p2p_delay = p2p_delay_value
            self._cline_delay = cline_delay_value
        else:
            self._p2p_delay = p2p_delay_value
            self._cline_delay = cline_delay_value

        return [0]

    def find_device_address(self):
        """ Methods finds device address and returns it if found.
            Otherwise returns False. """

        found = False

        for address in range(0x40, 0x7F):
            try:
                self.i2c.read(address, 1)
                found = True
            except I2CError:
                found = False
                #time.sleep(0.001)
            if found is True:
                return address

        return found

    def get_and_add_functions(self):
        """ Loops trough pages and gets all available functions for later use
        """

        for page in range(3):
            # set page
            self.i2c.write(self._address, [0xFF, page])
            self._current_page = page

            # get and add all functions from page
            for i in range(self._function_descriptions_address - 5, 0x00, -6):
                data = self.i2c.write_then_read(self._address, [i], 6)

                if data[5] > 0x00:
                    self.add_function(page, data)
                else:
                    break

    def add_function(self, page, data):
        """ Adds function info to dictionary """

        self._functions[data[5]] = {}

        self._functions[data[5]]['query'] = data[0]
        self._functions[data[5]]['control'] = data[2]
        self._functions[data[5]]['data'] = data[3]
        self._functions[data[5]]['command'] = data[1]
        self._functions[data[5]]['page'] = page
        self._functions[data[5]]['version'] = (data[4] >> 5) & 0x03
        self._functions[data[5]]['interrupts'] = data[4] & 0x07

    def read_register(self, register_type, function_name, read_offset, \
                      bytes_number, timeout=1000, wait_for_interrupt=False):

        """
        Reads specified register type from specified function.

            register_type:      QUERY, CONTROL, DATA or COMMAND
            function_name:      hex name of the function which is used
            read_offset:        read offset to the register's base address
            bytes_number:       number of bytes to read
            timeout:            timeout for waiting
            wait_for_interrupt: true / false

        """
        function_page = self._functions[function_name]['page']

        # change page if it is not right
        if self._current_page != function_page:
            self.i2c.write(self._address, [0xFF, function_page])
            self._current_page = function_page

        data = [self._functions[function_name][register_type] + read_offset]

        return self.i2c.write_then_read(self._address, data, bytes_number,
                                        timeout, wait_for_interrupt)

    def write_register(self, register_type, function_name, read_offset, \
                       bytes_number):
        """
        Writes to specified register.

            register_type:      QUERY, CONTROL, DATA or COMMAND
            function_name:      hex name of the function which is used for write
            read_offset:        offset to the register's base address
            bytes_number:       number of bytes to write
        """

        function_page = self._functions[function_name]['page']

        # change page if it is not right
        if self._current_page != function_page:
            self.i2c.write(self._address, [0xFF, function_page])
            self._current_page = function_page

        data = [self._functions[function_name][register_type] + read_offset]

        self.i2c.write(self._address, data + bytes_number)

    def read_status_registers(self):
        """
        Reads device status register and interrupt status register.
        Using this method clears Int Request bits in interrupt status register.
        """
        return self.read_register(DATA, 0x01, 0, 2)

    def TestMUX(self, panelcount):
        """ Writes DUT index to multiplexer and initialize the device
            @param panelcount: number of panels attached
        """
        read_status = []
        for index in range(panelcount):
            try:
                self.Multiplexer(index)
                self.Initialize()
            except I2CError:
                # custom exception I2CError; defined under i2c_driver.py
                read_status.append(index + 1)

        self.Multiplexer(0)
        return read_status

    def Multiplexer(self, index):
        """ Wrapper function, method called from I2C driver
            @param index: index of a device; default value is 0, ranges from
            0 to 7
        """
        self.i2c.write_multiplexer_index(index)
        return [index]

    def ReturnP2PArray(self, index=0, waitForFingerInterrupt=True):
        """ Returns p2p array
        """
        self.Multiplexer(index)

        # clear ints if found
        while self.i2c.read_interrupt_state()[0] == 0:
            self.read_status_registers()

        if self._2d_version == 0x11:
            return self.read_0x11_data(1, self._p2p_delay)
        else:
            return self.read_0x12_data(1, self._p2p_delay)

    def ReturnCLineArray(self, waitForFingerInterrupt=True):
        """A wraper function returning Cline array
        """
        if self._2d_version == 0x11:
            return self.read_0x11_data(0, self._cline_delay)
        else:
            return self.read_0x12_data(0, self._cline_delay)

    def p2p_interrupt(self, timeout):
        """ P2P test interrupt timestamps """

        start_time = time.time()
        # Wait to optical interrupt to come
        while True:
            if self.i2c.read_interrupt_state()[1] == 1 or \
               (start_time + timeout/1000) <= time.time():
                break
        timestamp_ext = self.i2c.read_timestamps()[1]
        i2c_timeout = 200

        return timestamp_ext, i2c_timeout

    def calculate_delay(self, timestamp_ext, i2c_timeout, test):
        """ Calculates delay """

        timestamp_I2C = self.i2c.read_timestamps()[0]
        delay = timestamp_I2C/ 1000.0

        return delay

    def read_0x11_data(self, test, timeout=1000):
        """ Reads coordinate data from 0x11 function """
        #register_count = self._supported_fingers * 8
        data_bytes_per_finger = 5

        panel_data = []
        errors = []
        data = []

        finger_mask = [(0, 0x03, 0), (0, 0x0C, 1), (0, 0x30, 2), (0, 0xC0, 3),
                       (1, 0x03, 4), (1, 0x0C, 5), (1, 0x30, 6), (1, 0xC0, 7),
                       (2, 0x03, 8), (2, 0x0C, 9)]

        touch_status = False

        reg_count = self._F11_2D_Data0_register_count

        try:
            loop = 0
            while loop < self._supported_fingers:

                if test == 1 and loop == 0:
                    timestamp_ext, i2c_timeout = self.p2p_interrupt(timeout)
                elif test == 1:
                    timestamp_ext = 0
                    i2c_timeout = 200              
                else:
                    timestamp_ext = 0
                    i2c_timeout = timeout

                loop += 1

                # This reads finger states according to the finger amount.
                # Size of this register has been calculated at initialize.
                # (self._F11_2D_Data0_register_count)
                finger_states = self.read_register(DATA, 0x11, 0,
                                                   reg_count,
                                                   timeout=i2c_timeout,
                                                   wait_for_interrupt=True)

                delay = self.calculate_delay(timestamp_ext, i2c_timeout, test)

                self.read_status_registers()

                # finger states are 0 if there's no finger present -> skip
                if not finger_states == reg_count * [0]:

                    for register_count_id, mask, finger_id in finger_mask:
                        if register_count_id < reg_count:

                            # check for active finger
                            # 4 different finger states can be in one byte
                            if finger_states[register_count_id] & mask > 0:

                                # read data from right offset
                                data = self.read_register(DATA, 0x11,
                                                        data_bytes_per_finger *
                                                        finger_id + reg_count,
                                                        data_bytes_per_finger)

                                x = (data[0] << 4) | (data[2] & 0x0F)
                                y = (data[1] << 4) | ((data[2] & 0xF0) >> 4)
                                z = data[4]

                                panel_data.append((x, y, z, finger_id, 0, \
                                                   delay,0))
                                touch_status = True

                if touch_status is True:
                    panel_data.append('OK')
                    panel_data.append('')
                    return panel_data

                elif touch_status is False:
                    errors.append('Interrupt was dummy...')

        except I2CError:
            raise Exception('read_0x11_data', 'No response in read_0x11_data')

        except Exception as Error:
            # if error, init and add details to return array
            panel_data[:] = []
            panel_data.append((0, 0, 0, 0, 0, 0, 0))
            panel_data.append(str(Error).replace("\'", ""))
            panel_data.append(str(finger_states + [99] + data + [99] + \
                                                                [reg_count]))
            return panel_data

        if touch_status is False:
            panel_data.append((0, 0, 0, 0, 0, 0, 0))
            panel_data.append('DUMMY')
            panel_data.append(str(errors))
            return panel_data

    def read_0x12_data(self, test, timeout=1000):
        """ Reads coordinate data from 0x12 function """

        register_count = self._supported_fingers * 8

        panel_data = []
        errors = []
        touch_status = False

        try:
            loop = 0
            while loop < 1:

                if test == 1 and loop == 0:
                    timestamp_ext, i2c_timeout = self.p2p_interrupt(timeout)
                else:
                    timestamp_ext = 0
                    i2c_timeout = timeout
                loop += 1

                # This reads each finger states to one list
                finger_states = self.read_register(DATA, 0x12, 0,
                                                   register_count,
                                                   timeout=i2c_timeout,
                                                   wait_for_interrupt=True)

                delay = self.calculate_delay(timestamp_ext, i2c_timeout, test)

                #self.read_status_registers()  # clear ints

                data = finger_states

                for finger_id in range(register_count/8):
                    if data[finger_id * 8] != 0:

                        # combine 8 bit value to 16 bit value: (MSB << 8) + LSB
                        x = (data[finger_id * 8 + 2] * 256) + \
                             data[finger_id * 8 + 1]
                        y = (data[finger_id * 8 + 4] * 256) + \
                             data[finger_id * 8 + 3]
                        z = data[finger_id * 8 + 5]

                        panel_data.append((x, y, z, finger_id, 0, delay, 0))
                        touch_status = True

                if touch_status is True:
                    panel_data.append('OK')
                    panel_data.append('')
                    return panel_data

                elif touch_status is False:
                    errors.append('Interrupt was dummy...')

        except I2CError:
            raise Exception('read_0x12_data', 'No response in read_0x12_data')

        except Exception as Error:
            # if error, init and add details to return array
            panel_data[:] = []
            panel_data.append((0, 0, 0, 0, 0, 0, 0))
            panel_data.append(str(Error).replace("\'", ""))
            panel_data.append(str(finger_states + [99] + data + [99] + \
                                 [register_count]))
            return panel_data

        if touch_status is False:
            panel_data.append((0, 0, 0, 0, 0, 0, 0))
            panel_data.append('DUMMY')
            panel_data.append(str(errors))
            return panel_data

    def WriteSleepMode(self, sleep_mode):
        """ Change modes
        @param sleep_mode: 1 = Active mode, 2 = Doze mode, 3 = Deep sleep mode
        """

        F01_RMI_Ctrl0 = self.read_register(CONTROL, 0x01, 0, 1)
        sleep_mode = F01_RMI_Ctrl0[0] & ~0x03  # normal operation

        # Read F11_2D_Ctrl0 register and clear lowest 3 bits (reporting mode)
        F11_2D_Ctrl0 = self.read_register(CONTROL, 0x11, 0, 1)
        report_mode = F11_2D_Ctrl0[0] & ~0x07

        # "Active mode"
        if sleep_mode == 1:
            # disable sleep mode
            self.write_register(CONTROL, 0x01, 0, [sleep_mode | 0x04])
            self.write_register(CONTROL, 0x11, 0, [report_mode])

        # "Doze mode"
        if sleep_mode == 2:
            # enable sleep mode
            self.write_register(CONTROL, 0x01, 0, [sleep_mode & ~0x04])

        #Deep Sleep
        if sleep_mode == 3:
            sleep_mode = F01_RMI_Ctrl0[0] & ~0x04 | 0x01
            self.write_register(CONTROL, 0x01, 0, [sleep_mode])

        return [0]

    def ReadFWVersion(self):
        """ Reads the Firmware version
        """
        F01_RMI_Query3 = self.read_register(QUERY, 0x01, 0, 4)

        status = []
        status.append((0, 0, 0, 0, 0, 0))
        status.append('Panel: ' + str(F01_RMI_Query3[3]))
        status.append('')

        return status

    def ReturnInterruptStates(self):
        """ Reads and returns the Interrupt states
        """
        state = []
        state = self.i2c.read_interrupt_state()
        return state
    
    def ReturnTimestamps(self):
        """ Wrapper function returning timestamps
        """
        timestamps = self.i2c.read_timestamps()
        timestamps = [x /1000.0 for x in timestamps]
        return timestamps + [timestamps[1]-timestamps[2]]
    
    def SingleTrigger(self):
        """ Sets single trigger mode
        """
        self.i2c.set_trigger([False, True, True, True])
        return 0
    
    def NormalTrigger(self):
        """ Sets normal trigger mode
        """
        self.i2c.set_trigger([True, True, True, True])
        return 0