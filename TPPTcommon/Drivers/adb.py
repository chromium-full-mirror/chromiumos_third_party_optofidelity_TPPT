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
import logging
import subprocess
import threading
import time
import os

log = logging.getLogger(__name__)

# Path to adb.exe. You should add the location of adb.exe to system path variable and it would be found.
# If this is not feasible or preferred for some reason, you can modify ADB_PATH, e.g., ADB_PATH = "C:\\Android\\adb.exe"
ADB_PATH = "adb"
# We will save all the lines from the Android ksmg log that contain this string
LOG_STRING = "[ FTS ]"
# Touch event type codes used in the rest of the system
ACTION_TOUCH_DOWN = 0
ACTION_LIFT_OFF = 1
ACTION_MOVE = 2

"""
Information and samples of adb getevent outputs from Google Pixel phone that this driver works with

Links to Android website:
- Specification of the events at https://source.android.com/devices/input/touch-devices
- See also https://source.android.com/devices/input/getevent

Getting information about touch device:
> adb exec-out getevent -lp /dev/input/event2
add device 1: /dev/input/event2
  name:     "synaptics_dsxv26"
  events:
    KEY (0001): KEY_WAKEUP
    ABS (0003): ABS_MT_SLOT           : value 0, min 0, max 9, fuzz 0, flat 0, resolution 0
                ABS_MT_TOUCH_MAJOR    : value 0, min 0, max 32, fuzz 0, flat 0, resolution 0
                ABS_MT_TOUCH_MINOR    : value 0, min 0, max 32, fuzz 0, flat 0, resolution 0
                ABS_MT_POSITION_X     : value 0, min 0, max 1079, fuzz 0, flat 0, resolution 0
                ABS_MT_POSITION_Y     : value 0, min 0, max 1919, fuzz 0, flat 0, resolution 0
                ABS_MT_TRACKING_ID    : value 0, min 0, max 65535, fuzz 0, flat 0, resolution 0
                ABS_MT_PRESSURE       : value 0, min 0, max 255, fuzz 0, flat 0, resolution 0
  input props:
    INPUT_PROP_DIRECT
    
    
Getting infromation about the touch events (simple quick one finger tap):
> adb exec-out getevent -lt /dev/input/event2
[     402.403250] EV_ABS       ABS_MT_TRACKING_ID   0000000a
[     402.403250] EV_ABS       ABS_MT_POSITION_X    0000016c
[     402.403250] EV_ABS       ABS_MT_POSITION_Y    00000492
[     402.403250] EV_ABS       ABS_MT_PRESSURE      00000035
[     402.403250] EV_SYN       SYN_REPORT           00000000
[     402.417578] EV_ABS       ABS_MT_PRESSURE      0000003b
[     402.417578] EV_SYN       SYN_REPORT           00000000
[     402.426136] EV_ABS       ABS_MT_PRESSURE      0000003a
[     402.426136] EV_SYN       SYN_REPORT           00000000
[     402.434663] EV_ABS       ABS_MT_PRESSURE      0000003b
[     402.434663] EV_SYN       SYN_REPORT           00000000
[     402.450790] EV_ABS       ABS_MT_PRESSURE      00000039
[     402.450790] EV_SYN       SYN_REPORT           00000000
[     402.459181] EV_ABS       ABS_MT_TRACKING_ID   ffffffff
[     402.459181] EV_SYN       SYN_REPORT           00000000

"""

class Adb:

    PROCESS_IDLE_TIMER = 360 #s

    class TouchEvent:
        """
        A structure to describe a single touch event.
        """

        def __init__(self):
            """
            Constructor.
            """
            self.has_changed = False
            self.x = None
            self.y = None
            self.pressure = None
            self.action = None
            self.tracking_id = None
            self.finger_id = None

        def all_have_values(self):
            """
            Checks if all the object variables have values (except has_changed). If value is lacking
            it might indicate that there is an issue with initialisation of the slot data
            :return: True if all the variables have values, False if they don't
            """
            # The DUT might not have (but can have) pressure field so we need give it a value
            # if there is none to avoid issues with legacy code
            if self.pressure is None: self.pressure = 0

            if self.x is not None and self.y is not None and self.action is not None \
                    and self.tracking_id is not None and self.finger_id is not None:
                return True
            else:
                return False


    def __init__(self):
        """
        Constructor.
        """
        """
        Timer monitoring how long it's been since last operation was requested from ADB and stops ADB processes
        if PROCESS_IDLE_TIMER is exceeded
        """
        self.timer = None

        """ Final log buffer between start_log and stop_log. """
        self._log_buffer = ""
        """ Temporary log buffer where log data is collected as it is received. """
        self._log_buffer_tmp = ""
        """ Thread for log collection. """
        self._log_thread = None
        """ Process for log collection. This is run in the log thread. """
        self._log_process = None

        """ Temporary log buffer where log data is collected as it is received. """
        self._touch_event_buffer_tmp = []
        """ Thread for touch event collection. """
        self._touch_event_thread = None
        """ Process for touch event collection. This is run in the touch event thread. """
        self._touch_event_process = None

        """ List of available touch events for tools. It contains touchevent instances per slot id. The system """
        """ reuses old values with same slot id (if not changed), so this cannot be emptied between measurements """
        self._slot_data_cache = {}

        """ Ensuring finger ids are not reused, this is reset for every recording"""
        self._next_finger_id = None

        """ All the values are connected to current slot id and the slot id is not given unless it changes """
        self._current_slot_id = None
        """ Bookkeeping of which slot ids are active """
        self._active_slot_ids = set()

        """ We need to know the previous event to handle SLOT case correctly"""
        self._previous_event = None

        """ Min and max values for ABS_MT_POSITIONS, used for calculating the correct coordinates"""
        self._MT_minX = None
        self._MT_maxX = None
        self._MT_minY = None
        self._MT_maxY = None

        """ The event ID we are tracking with adb getevent """
        self._event_id = None

        """ Display settings """
        self._display_width = None
        self._display_height = None

    def _run_process(self, exe, process: str):
        if process == "log":
            # The logging process needs to be run as root and for that we need to use shell command "&&"
            # If shell = True the manual says: "The shell argument (which defaults to False) specifies whether
            # to use the shell as the program to execute. If shell is True, it is recommended to pass args as a string
            # rather than as a sequence".
            process_string = ""
            for part in exe:
                process_string += part + " "
            p = subprocess.Popen(process_string, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
            log.debug("Subprocess (PID={}) started for command (process={}): {}".format(p.pid, process, exe))
            self._log_process = p
        else:
            p = subprocess.Popen(exe, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.debug("Subprocess (PID={}) started for command (process={}): {}".format(p.pid, process, exe))
            assert process == "touch_event"
            self._touch_event_process = p

        try:
            # .poll returns None if the process is still running so we can use it
            # to stop reading lines after the process in finished
            running = None
            while running is None:
                running = p.poll() # This blocks until subprocess has something to return
                line = p.stdout.readline()
                # TODO: Handle empty data somehow by maybe quiting after 5 empty lines etc.
                yield line
        except ValueError as e:
            log.debug("Subprocess (PID={}) closed for command: {}".format(p.pid, exe))

    def _log_process_run(self):
        for s in self._run_process([ADB_PATH, "root", "&&", ADB_PATH, "shell", "cat", "/dev/kmsg"], "log"):
            try: # it is possible we get something that cannot be decoded
                if s.decode("UTF-8").find(LOG_STRING) != -1:
                    self._log_buffer_tmp = self._log_buffer_tmp + s.decode("UTF-8")
            except:
                pass

    def initialize_settings(self, display_width = None, display_height = None, adb_event = None):
        '''
        Ensures that the input event that will be connected is compliant with the adb parsing.
        This is done by checking that all the required fields are provided by the input event.
        Additionally, finds the minX/maxX and minY/maxY values for calculating the coordinates
        and save the display width and height provided by the function call
        :param display_width: the width of the display in pixels (~ resolution)
        :param display_height: the height of the display in pixels (~ resolution)
        :param adb_event: the event adb is following, for example event2
        :return: True if everything went well and False if there are some issues
        '''
        if adb_event is not None:
            self._event_id = adb_event
        else:
            log.error("Adb driver init: adb event id not given")
            return False

        event_fields = []
        expected_event_fields = ['ABS_MT_SLOT', 'ABS_MT_POSITION_X', 'ABS_MT_POSITION_Y',
                                 'ABS_MT_TRACKING_ID']
        exe_command = [ADB_PATH, "exec-out", "getevent", "-lp", "/dev/input/"+self._event_id]

        p = subprocess.Popen(exe_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.debug("Subprocess (PID={}) started for command (process={}): {}".format(p.pid, "compatibility_check", exe_command))

        # Read output and wait for process to terminate.
        stdout, _ = p.communicate()
        stdout = stdout.decode('ascii')

        log.debug("Subprocess finished")

        # Going through the output lines from the process
        for line in stdout.splitlines():
            if line is None: break
            for field in line.split():
                if "ABS_MT" in field:
                    event_fields.append(field)
                    self._parse_MT_min_max_values(line)

        # Removing all the found events from the expected list
        for event in event_fields:
            if event in expected_event_fields: expected_event_fields.remove(event)

        if display_height is not None:
            self._display_height = display_height
        else:
            log.error("Adb driver init: display height not given")
            return False
        if display_width is not None:
            self._display_width = display_width
        else:
            log.error("Adb driver init: display width not given")
            return False

        if len(expected_event_fields) != 0:
            log.error("Adb driver init: all the requested ABS_MT fields not found")
            return False
        elif self._MT_minX is None or self._MT_maxX is None or self._MT_minY is None or self._MT_maxY is None:
            log.error("Adb driver init: failed the get all the MT_min/MT_max values")
            return False
        else:
            return True


    def _parse_MT_min_max_values(self, line):
        """
        Checks if the given line contains information about ABS_MT_POSITIONs and
        parses the min/max values from the line if needed. Saves them to class variables
        :param line:
        :return:
        """
        fields = line.split()
        # The positions might be given already in the first field that starts differently
        # In that case we take the unnecessary fields away and continue as usual
        if fields[0] == 'ABS':
            index = None
            if 'ABS_MT_POSITION_X' in fields: index = fields.index('ABS_MT_POSITION_X')
            elif 'ABS_MT_POSITION_Y' in fields: index = fields.index('ABS_MT_POSITION_Y')
            if index is not None:
                for i in range(index):
                    fields.pop(0)
        # Parsing the min/max values
        if fields[0] == 'ABS_MT_POSITION_X':
            min_index = fields.index('min')
            max_index = fields.index('max')
            self._MT_minX = int(fields[min_index + 1].strip(','))
            self._MT_maxX = int(fields[max_index + 1].strip(','))
        elif fields[0] == 'ABS_MT_POSITION_Y':
            min_index = fields.index('min')
            max_index = fields.index('max')
            self._MT_minY = int(fields[min_index + 1].strip(','))
            self._MT_maxY = int(fields[max_index + 1].strip(','))
        else:
            pass

    def create_touch_event(self, touchevent, timestamp):
        '''
        Formats data from touchevent data container to the legacy format of the system
        :param touchevent: instance of TouchEvent, "data container"
        :param timestamp: we give timestamp separately so that we don't need to update it all the
        time to the data container. This works because the timestamp is given in the beginning of all the lines
        :return: formatted list
        '''
        # Generate a python list with the following elements to comply with the data formats that has been used:
        # 0: (468.4131,1017.48047,0.50390625,0,0,508350234,0,0.0,0.0,0.0)
        # 1: 'OK'
        # 2: ''
        try:
            if touchevent.all_have_values():
                touch_event = [ \
                    (touchevent.x,
                     touchevent.y,
                     touchevent.pressure,
                     touchevent.finger_id,
                     0,
                     timestamp,
                     touchevent.action,
                     0.0,
                     0.0,
                     0.0),
                    "OK",
                    ""]
                return touch_event
            else:
                log.error("Adb driver create_touch_event: Touch event missing data. Not sending data")
                return None
        except:
            log.error("Adb driver create_touch_event: Something wrong with the touch event object. Not sending data")
            return None

    def parse_getevent(self, line):
        '''
        Parses one line that is received from dut via adb
        :param line:
        :return: list of touch events that have changed between SYN_REPORTs
        '''
        touch_events = []

        if len(line) == 0:
            return touch_events

        parts = line.split()
        # TODO: Timestamp is in milliseconds in microsecond accuracy while it used to be in milliseconds with millisecond accuracy
        # Check does this break something?
        timestamp = parts[1][:-1] # timestamp in seconds
        timestamp = str(float(timestamp)*1000) # seconds -> milliseconds
        event = parts[3]
        value = parts[4]

        if event == "ABS_MT_TRACKING_ID":
            # ABS_MT_TRACKING_ID  reports the tracking id of the tool. However, we have our own finger_id we track
            # and SLOT is used to cache the events, so we use tracking id to denote touch downs and lift offs.
            # If tracking id is given non-negative value, it means that I new device has touched to screen
            # value "ffffffff" means lift off

            if value != "ffffffff": # there is a new tool touching the screen
                if len(self._active_slot_ids) == 0:
                    # There are no active slot_ids so the new touch will
                    # get slot 0 by default without "ABS_MT_SLOT" field
                    self._current_slot_id = "00000000"
                    self._active_slot_ids.add(self._current_slot_id)

                if self._current_slot_id not in self._slot_data_cache:
                    # there is no data yet for the specific slot
                    # creating a placeholder in the tool tracking list
                    self._slot_data_cache[self._current_slot_id] = self.TouchEvent()

                # Setting the new values for current slot_id
                self._slot_data_cache[self._current_slot_id].finger_id = self._next_finger_id
                self._next_finger_id += 1
                self._slot_data_cache[self._current_slot_id].action = ACTION_TOUCH_DOWN
                self._slot_data_cache[self._current_slot_id].tracking_id = value

            else: # value == 'ffffffff' -> finger has gotten up
                assert value == "ffffffff"
                self._slot_data_cache[self._current_slot_id].action = ACTION_LIFT_OFF
                # The touch event is ready and will be passed forward
                self._active_slot_ids.remove(self._current_slot_id)

        elif event == "ABS_MT_SLOT":
            # ABS_MT_SLOT is used to separate different tools touching the screen (MT = multitouch)
            # The data is cached per slot id and is reused even if the tool has changed. The cached data
            # is emptied only during reboot.

            # SLOT might be the very first field we get if already during the first timestamp there are two
            # tools touching the screen and in that case we need to do things differently
            if value not in self._slot_data_cache:
                self._current_slot_id = value
                self._slot_data_cache[self._current_slot_id] = self.TouchEvent()

            # It is possible that we get data only from one of the active slots for many timestamps.
            # In that case, we need to set the SLOT.has_changed flag here if the slot data has changed between
            # SYN_REPORT and SLOT
            if self._previous_event != "SYN_REPORT":
                self._slot_data_cache[self._current_slot_id].has_changed = True

            # Always when we get the slot id information, we are going the get data connected to the id
            self._current_slot_id = value
            self._slot_data_cache[self._current_slot_id].has_changed = True
            self._active_slot_ids.add(value)


        elif event == "ABS_MT_POSITION_X":
            # From https://source.android.com/devices/input/touch-devices:
            #     displayX = (x - minX) * displayWidth / (maxX - minX + 1)
            x = int(value, 16)
            x_pixels = (x - self._MT_minX) * self._display_width / (self._MT_maxX - self._MT_minX + 1)
            self._slot_data_cache[self._current_slot_id].x = x_pixels

        elif event == "ABS_MT_POSITION_Y":
            # From https://source.android.com/devices/input/touch-devices:
            #     displayY = (y - minY) * displayHeight / (maxY - minY + 1)
            y = int(value, 16)
            y_pixels = (y - self._MT_minY) * self._display_height / (self._MT_maxY - self._MT_minY + 1)
            self._slot_data_cache[self._current_slot_id].y = y_pixels

        elif event == "ABS_MT_PRESSURE":
            # Store pressure value as decimal value
            pressure = int(value, 16)
            self._slot_data_cache[self._current_slot_id].pressure = pressure

        elif event == "SYN_REPORT":
            # SYN_REPORT indicates that all the data for current timestamp is given

            # If we only have something to report from one of the slots for many timestamps
            # in a row, we need to set the slot_data.has_changed flag here to send the correct data
            self._slot_data_cache[self._current_slot_id].has_changed = True

            # Send all the data for the slots that have changed during current timestamp and
            # take the slot_data.has_changed flags away. It is also the best to set the action to
            # ACTION_MOVE here so that touch down and lift off occur only once.
            for slot_data in self._slot_data_cache.values():
                if slot_data.has_changed:
                    touch_event = self.create_touch_event(slot_data, timestamp)
                    if touch_event is not None:
                        touch_events.append(self.create_touch_event(slot_data, timestamp))
                    slot_data.has_changed = False
                    slot_data.action = ACTION_MOVE

        self._previous_event = event
        return touch_events

    def _touch_event_process_run(self):
        try:
            for s in self._run_process([ADB_PATH, "exec-out", "getevent", "-lt", "/dev/input/"+self._event_id], "touch_event"):
                touch_data = self.parse_getevent(s.decode("ascii"))
                if len(touch_data) != 0:
                    for data_set in touch_data:
                        self._touch_event_buffer_tmp.append(data_set)
        except Exception:
            # Handle all exceptions and log them because exceptions are not propagated to the main thread.
            log.exception("Error in handling touch events.")

    def _restart_timer(self):

        if self.timer is not None and self.timer.is_alive():
            self.timer.cancel()

        # TODO: Consider more robust way of terminating idle processes.
        # At the moment it is possible that timer kills the touch event process
        # in between start_touch_events() and stop_touch_events().
        self.timer = threading.Timer(Adb.PROCESS_IDLE_TIMER, self._stop)
        self.timer.start()

    def start_log(self):
        """
        Start log collection.
        :return: Nothing.
        """
        if self._log_thread is None:
            self._log_thread = threading.Thread(target=self._log_process_run)
            log.debug("Starting log thread name={}".format(self._log_thread.name))
            self._log_thread.start()
        # NOTE: Even though we empty the buffer after startup of the logging, we cannot be sure
        # that there is no leakage of earlier events from the log ring buffer. This means that the
        # very first log entry probably contains data from before the start_log command
        self._log_buffer_tmp = ""

    def stop_log(self):
        """
        Stop log collection and return collected log buffer between start and stop calls.
        :return: Log buffer.
        """
        self._log_buffer = self._log_buffer_tmp
        self._restart_timer()
        return self._log_buffer

    def start_touch_events(self):
        """
        Start collection of touch events. The process is running all the time
        so we just check that the process is ok, empty the buffer and set finger_id to 0
        :return: Nothing.
        """
        self._touch_event_buffer_tmp = []
        # finger_ids start from zero for each recording
        self._next_finger_id = 0
        if self._touch_event_thread is None:
            self._touch_event_thread = threading.Thread(target=self._touch_event_process_run)
            log.debug("Starting touch event thread name={}".format(self._touch_event_thread.name))
            self._touch_event_thread.start()
            log.debug("Started succesfully touch event thread name={}".format(self._touch_event_thread.name))
        # Since we are doing touch event process in different thread,
        # we need to check if it is running before continuing
        while self._touch_event_process is None:
            time.sleep(0.5)

    def get_touch_events(self):
        return self._touch_event_buffer_tmp.copy()

    def stop_touch_events(self):
        """
        Stop collection of touch events.
        :return: Touch events.
        """
        touch_event_buffer = self.get_touch_events()
        self._restart_timer()
        return touch_event_buffer

    @staticmethod
    def _kill_process_recursively(process):
        """
        Kill process and its child processes.
        :param process: Process previously created with Popen().
        """
        # TODO: This is platform dependent and currently only Windows is supported.
        assert (os.name == "nt")

        p = subprocess.Popen("TASKKILL /F /PID {pid} /T".format(pid=process.pid))
        p.communicate()

    def _stop(self):
        """
        Stops adb processes if they are running.
        :return:  Nothing.
        """
        log.debug("Stop triggered for adb.exe processes")

        # We have to kill both processes before communicate because communicate would get stuck
        # because stdout PIPE is not finished and communicate waits for that
        if self._log_process is not None:
            log.debug("Killing log process")
            # kill() does not seem to be effective as log process is started with shell=True.
            Adb._kill_process_recursively(self._log_process)

            self._log_process.communicate()
            self._log_process = None
            log.debug("Killed log process")

        if self._touch_event_process is not None:
            log.debug("Killing touch event process")
            self._touch_event_process.kill()

            self._touch_event_process.communicate()
            self._touch_event_process = None
            log.debug("Killed touch event process")

        if self._log_thread is not None:
            log.debug("Joining log thread")
            self._log_thread.join()
            self._log_thread = None
            log.debug("Joined log thread")

        if self._touch_event_thread is not None:
            log.debug("Joining touch event thread")
            self._touch_event_thread.join()
            self._touch_event_thread = None
            log.debug("Joined touch event thread")

    def get_log_buffer(self):
        return self._log_buffer

