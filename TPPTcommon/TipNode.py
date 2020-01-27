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
from .Node import *

class TipNode(Node):
    """
    Node that represents robot tip.
    """

    def __init__(self, name, tnt_tip):
        super().__init__(name)
        self.tnt_tip = tnt_tip
        self.display_enabled = True
        self.enabled = False

class TipsNode(Node):
    """
    Node that hosts tip nodes as children and keeps track of current robot tip.
    """

    def __init__(self, context):
        super().__init__('Tips')

        self.active_tip = None
        self.context = context

    def create_tips(self):
        """
        Create a group of controls for enabling tips for tests.
        """

        # Get tip definitions from server.
        tips = self.context.tnt.tips()

        tips.sort(key=lambda t: t.name)

        for tip in tips:
            tip_node = TipNode(tip.name, tip)

            self.add_child(tip_node)

    def set_active_tip(self, tip_node):
        """
        Set active tip to be used by test cases.
        Makes robot to physically change tip if appropriate.
        :param tip_node: Tip node to set active.
        """

        tip = tip_node.tnt_tip

        # Set active ip state.
        self.active_tip = tip

        self.context.html_color("Picking tip: " + str(self.active_tip), 'orange')

        prev_status = self.context.indicators.get_status()
        self.context.indicators.set_status("Changing tip to " + str(self.active_tip))
        self.context.indicators.set_tip_name(str(self.active_tip))

        # Make robot change tip.
        try:
            self.context.set_robot_default_speed()
            self.context.robot.change_tip(self.active_tip)
        except Exception as ex:
            self.context.html_color("Tip " + str(self.active_tip) + " is already mounted. Continuing testing.", 'orange')
        finally:
            self.context.indicators.set_status(prev_status)

    def set_active_tip_by_name(self, tip_name):
        self.set_active_tip(self.get_child(tip_name))

    def check_tips(self):
        """
        Check that at least one tip is enabled.
        """

        for tip in self.children:
            if tip.enabled:
                return True

        return False

    def find_by_name(self, name):
        """
        Finds tip object by its name.
        :param name: the name of the tip
        :return: the tip object or None (if tip is not found)
        """
        tip = None
        for tip_object in self.children:
            if tip_object.name == name:
                tip = tip_object
                break
        return tip

