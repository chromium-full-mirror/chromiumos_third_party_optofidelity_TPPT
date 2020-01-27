"""
OF TEPA USB panel driver


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

from fpga_driver import *
import time
import hid

class USBError(Exception):
    '''SPI error occurred'''
    ERR_EXT_IRQ_TIMEOUT = 9998
    ERR_USB_RECEIVE_TIMEOUT = 9997
    
    def __init__(self, errorcode):
        str = "Unknown USB error"
        if errorcode == self.ERR_EXT_IRQ_TIMEOUT:
            str = "External interrupt timeouted"
        elif errorcode == self.ERR_USB_RECEIVE_TIMEOUT:
            str = "USB receive timeouted"
        
        Exception.__init__(self, errorcode, str)

    def get_code(self):
        '''Get the error code, one of the ERR_* data members of this class.'''
        return self.args[0]


class device_driver:
    '''Driver OF TEPA panel with Atmel controller'''
    LastTimeStamp = 0
    scr = {"user":"MJU", "ver":"1.0", "date":"2014-10-23"}
    DelayP2P = 0
    DelayCLine = 0
    PreviousButton = 0

    def __init__(self, fpga, fsession):
        """ Initialize stuff here """
        # Init stuff here 
        self.hid = 0
        self.fpga = fpga
        self.fsession = fsession
        self.strigger = 0

    def __del__(self):
        """ Close device if open """
        #if self.fpga_session:
        close_usb()
        if self.hid:
            self.hid.close()
            self.hid = 0

    def TestMUX(self,panelcount):
        """ Only one USB device available"""
        return []

    def Multiplexer(self,index):
        """ Change active MUX """
        #self.fpga_session = init_usb("/home/admin/NiFpga_myRIO1900CustomizedFPGA")
        return [self.fsession]

    def Initialize(self, Setup = 0):
        """ Run by executing command 'InitializePanel'
        Initialize panel and chip.
        Use Input parameter to choose corresponding setup if different setups are possible.
        Return 0 if passed, exception if error"""
        self.strigger = 0
        fpga.read_ext_rise_fall([True, False, True, True, True])
        
        # Enumerate devices
        hidenum = []
        for d in hid.enumerate(0, 0):
            keys = d.keys()
            keys.sort()
            for key in keys:
                hidenum.append("%s : %s" % (key, d[key]))
        
        try:
            self.hid = hid.device(0x03eb, 0x2128, self.fsession)
            devinfo = []
            devinfo.append("Manufacturer: %s" % self.hid.get_manufacturer_string())
            devinfo.append("Product: %s" % self.hid.get_product_string())
            devinfo.append("Serial No: %s" % self.hid.get_serial_number_string())
        except IOError as ex:
            raise Exception('Initialize error', ex)
            #USBError(9998)
        # set non-blocking mode
        self.hid.set_nonblocking(1)
        
        return [self.fsession, self.hid]
    
    def readHIDData(self):
        data = self.hid.read(60)
        if not data[0]:
            return []
        return [data[1], data[0]]
        
    def ReturnP2PArray(self, index = 0, waitForFingerInterrupt = True):
        """ Wait for touch
        Delay is time between first panel interrupt and external interrupt
        Return measured values:
        [(X, Y, Z, Finger index, delay, timestamp), (X, Y, Z, Finger index, delay, timestamp), 'note', 'log'] """
        
        CollectTuples = []
        try:
            # Flush old data
            flush_count = 0
            StartTime = time.time()
            while (self.readHIDData() != []):
                flush_count += 1
                if StartTime + 0.01 <= time.time():
                    CollectTuples.append((0,0,0,0,0,0))
                    CollectTuples.append("DUMMY")
                    CollectTuples.append('Flush error!! Ghost coordinates.')
                    return CollectTuples
            
            Time2 = (time.time() - StartTime) * 1000
            
            timeout = 6000
            StartTime = time.time()
            
            # Wait to optical interrupt to come
            touchdata = []
            while True:
                buf = self.readHIDData()
                if buf:
                    touchdata.append(buf)
                    
                if self.fpga.read_interrupt_state()[1] == 1 or StartTime + timeout/1000 <= time.time():
                    timestampExt = self.fpga.read_timestamps()[1]
                    break
            
            # Give up, if time out occurred.
            if (StartTime + timeout/1000 > time.time()):
                # Read coordinate after optical interrupt
                timeout = 1000
                StartTime = time.time()
                while StartTime + timeout/1000 > time.time():
                    buf = self.readHIDData()
                    if buf:
                        touchdata.append(buf)
                        break
                
                if touchdata == []:
                    raise USBError(9998)
                  
                fingerDelay = 0 # This is added in higher level.
                timestampExt = timestampExt - fingerDelay
                timestampI2C = self.fpga.read_timestamps()[2]
                for tdata in touchdata:
                    if self.strigger or tdata[0] > timestampExt:
                        data = tdata[1]
                        timestampUSB = tdata[0]
                        x = ((data[3]) << 8) + data[2]
                        y = ((data[5]) << 8) + data[4]
                        z = 0
                        delay = float((timestampUSB - timestampExt) / 1000.0)
                        CollectTuples.append((x, y, z, 0, delay, timestampUSB/1000, 0))
                        CollectTuples.append('OK') # note
                        CollectTuples.append(str("")) # log
                        break
            else:
                raise USBError(9998) 
        
        except USBError as ex:
            # if no interrupt, init and raise exception
            raise Exception('Time out', ex)

        except Exception as Detail:
            # if error, init and add details to return array
            CollectTuples[:] = []
            CollectTuples.append((0, 0, 0, 0, 0, 0, 0))
            CollectTuples.append(Detail)
            CollectTuples.append(str(""))
        
        return CollectTuples


    def ReturnCLineArray(self, waitForFingerInterrupt = True):
        """ Wait for touch
        Delay is time between this and previous touch
        Return measured values:
        [(X, Y, Z, Finger index, delay, timestamp), (X, Y, Z, Finger index, delay, timestamp), 'note', 'log'] """
        CollectTuples = []
        timeout = 4000
        
        try:     
            StartTime = time.time()
            while (StartTime + 4 > time.time()):
                buf = self.readHIDData()
                if buf != []:             
                    data = buf[1]
                    timestampUSB = buf[0]
                    delay = float(self.fpga.read_PanelInterruptDelay()[0]) / 1000.0
                    fingers = 0
                    index = 0
                    while (fingers < 8):
                        fingers += 1
                        x = ((data[3+index]) << 8) + data[2+index]
                        y = ((data[5+index]) << 8) + data[4+index]
                        z = 0
                        if (x != 0 or y != 0):
                            CollectTuples.append((x, y, z, fingers, delay, timestampUSB/1000, 0))
                            index += 7
                        else:
                            break
                        
                    CollectTuples.append('OK') # note
                    CollectTuples.append(str("")) # log
                    break
            
            if (StartTime + 4 < time.time()):
                raise USBError(9997)
        
        except USBError as ex:
            # if no interrupt, init and raise exception
            raise Exception('Time out', ex)
        
        except Exception as Detail:
            # if error, init and add details to return array
            CollectTuples[:] = []
            CollectTuples.append((self.LastTimeStamp, 0, 0, 0, 0, 0, 0))
            CollectTuples.append(Detail)
            CollectTuples.append("abc")
        
        return CollectTuples

    def ReturnButton(self, ResetBuffer = False):
        """ Get button status """
        
        return []

    def WriteSleepMode(self, SleepMode):
        return [0]


    def ReadFWVersion(self):
        """ Return chip fw and this script versions. Also date created and user name """

        status = []
        InfoBlock = [0,0,0,0]
        fw = "0x%02X build:0x%02X" % (InfoBlock[2], InfoBlock[3])
        status.append((0,0,0,0,0,0))
        status.append("Panel: " + fw + ", Script: " + self.scr['ver'] + ", User: " + self.scr['user'] + ", Date: " + self.scr['date'])
        status.append("")

        return status


    def ReadFWVersionAll(self):
        ret = ["poo"]
        return ret

    def ReturnInterruptStates(self):
        """ Return read_interrupt_state to main sw """

        state = []
        state = self.fpga.read_interrupt_state()
        return state
    
    def ReturnTimestamps(self):
        timestamps = self.fpga.read_timestamps()
        timestamps = [x /1000.0 for x in timestamps]
        return timestamps + [timestamps[1]-timestamps[2]]
    

    def SingleTrigger(self):
        self.strigger = 1
        self.fpga.set_trigger([False,True,True,True])
        return 0
    
    def NormalTrigger(self):
        self.strigger = 0
        self.fpga.set_trigger([True,True,True,True])
        return 0
    
    def ClearBuffer(self):
        try:
            StartTime = time.time()
            while (self.readHIDData() != []):
                if StartTime + 0.01 <= time.time():
                    raise USBError(9998)
        except USBError:
            pass
            
    def SNR(self, samples, touch, xNodes = 0, yNodes = 0):
        return [] #self.Touch.SNR(samples, touch, xNodes, yNodes)

global session, fpga       
fpga = FPGADriver(0)
session = init_fpga("/home/admin/NiFpga_myRIO1900CustomizedFPGA")
driver = device_driver(fpga, session)


