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
import os
from .Node import *
from scriptpath import get_script_root_directory


class DutNode(Node):
    """
    Node that represents DUT.
    Defines some DUT properties such as resolution and  measurement driver.
    """

    def __init__(self, name, tnt_dut):
        super().__init__(name)

        self.tnt_dut = tnt_dut

        pit_drivers_path = os.path.join(get_script_root_directory(), "TPPTcommon", "PIT_Drivers")
        pit_drivers = os.listdir(pit_drivers_path)

        self.display_enabled = True

        self.controls.driver = 'Adb'
        self.controls.info['driver'] = {'label': 'Driver', 'items': ['Adb', 'TCP socket', 'PIT', 'Dummy']}

        self.controls.adb_event_id = 'event2'
        self.controls.info['adb_event_id'] = {'label':'Adb event'}

        self.controls.pit_driver = pit_drivers[0]
        self.controls.info['pit_driver'] = {'label': 'PIT driver', 'items': pit_drivers}

        self.controls.pit_slot = 0
        self.controls.info['pit_slot'] = {'label': 'PIT slot', 'items': [1,2,3,4,5,6,7,8]}

        self.controls.fetch_resolution = True
        self.controls.info['fetch_resolution'] = {'label': 'Fetch device resolution automatically'}

        self.controls.dut_resolution = [800, 600]
        self.controls.info['dut_resolution'] = {'label': 'DUT resolution [x;y, p.c.]', "type": "double_number", "min": 1, "step": 1}

        self.controls.offset = [0, 0]
        self.controls.info['offset'] = {'label': 'DUT offset [x;y, mm]', "type": "double_number", "step": 1}

        self.controls.flip_x = False
        self.controls.info['flip_x'] = {'label': 'Flip X coordinates'}

        self.controls.flip_y = False
        self.controls.info['flip_y'] = {'label': 'Flip Y coordinates'}

        self.controls.flip_x_and_y = False
        self.controls.info['flip_x_and_y'] = {'label': '(X,Y) --> (Y,X)'} # Rotate by 90 deg and flip other coordinate.

    @property
    def resolution(self):
        return self.controls.dut_resolution

    @property
    def pit_index(self):
        """
        Get index for PIT. This is PIT slot - 1.
        :return:
        """
        return self.controls.pit_slot - 1

class DutsNode(Node):
    """
    Node that hosts DUT nodes as children and keeps track of current robot DUT.
    """

    def __init__(self, context):
        super().__init__('Duts')

        self.active_dut = None
        self.active_dut_node = None
        self.context = context

    def create_duts(self):
        """
        Create controls for enabling DUTs for tests and for setting their properties.
        """

        # Get DUT definitions from server.
        try:
            duts = self.context.tnt.duts()

            for dut in duts:
                dut.robot = self.context.robot
        except:
            self.context.html_color("No connection to TnT server. Please start TnT server and reload the script", "red")
            raise Stop("No connection to TnT server. Please start TnT server and reload the script")

        for dut in duts:
            # DUT named "OF" is special and not listed in GUI.
            # This is a device that is used to calibrate latency test.
            if dut.name == "OF":
                continue

            dut_node = DutNode(dut.name, dut)
            dut_node.enabled = False
            self.add_child(dut_node)

            # Indicators showing DUT sizes
            #setattr(self.indicators, dut.name + "_dutDimensions", str(round(dut.width, 2)) + ";" + str(round(dut.height, 2)))
            #self.indicators.label(dut.name + "_dutDimensions", dut.name + " dimensions [x;y, mm]")

    def set_active_dut(self, dut_node):
        """
        Set active DUT to be used by test cases.
        Makes required DUT initializations.
        :param dut_node: DUT node to set.
        """

        dut = dut_node.tnt_dut
        self.active_dut_node = dut_node

        # Set active DUT state.
        self.active_dut = dut

        if dut_node.controls.driver[:3] == "PIT":
            self.context.initialize_pit()

        res = dut_node.resolution
        self.context.create_dut_visualization(*res)

    def check_duts(self):
        """
        Check that at least one DUT is enabled.
        """

        for dut in self.children:
            if dut.enabled:
                return True

        self.context.html_color("No DUTs selected!", color="red")

        return False

    @property
    def active_driver(self):
        return self.active_dut_node.controls.driver