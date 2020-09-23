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
from collections import defaultdict
from TPPTcommon.exceptions import TipSelectionError

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

        # Dictionary of finger size -> single-finger tip nodes available with that size
        self.single_tips_by_size = defaultdict(list)

        # Dictionary of finger size -> multi-finger tip nodes available with that size
        self.multi_tips_by_size = defaultdict(list)

        # Dictionary of finger count -> multi-finger tip nodes available with that size
        self.multi_tips_by_count = defaultdict(list)

    def create_tips(self):
        """
        Create a group of controls for enabling tips for tests.
        """

        # Get tip definitions from server.
        tips = self.context.tnt.tips()

        tips.sort(key=lambda t: t.name)

        for tip in tips:
            tip_node = TipNode(tip.name, tip)
            diameter_str = "{:.1f}".format(tip.diameter)
            if not tip.is_multifinger:
                self.single_tips_by_size[diameter_str].append(tip_node)
            else:
                self.multi_tips_by_size[diameter_str].append(tip_node)
                self.multi_tips_by_count[tip.num_tips].append(tip_node)

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

    def _select_multi_finger_tip_by_size(self, finger_size, num_fingers, check_only):
        """
        Select a multi-finger tip matching the parameters.
        If check_only is True, don't actually select tips, but still raise exceptions as normal.
        """
        matching_tips = self.multi_tips_by_count[num_fingers]
        for tip_node in matching_tips:
            if tip_node.tnt_tip.diameter == float(finger_size):
                if not check_only:
                    self.set_active_tip(tip_node)
                return

        raise TipSelectionError("Tip not found with the correct diameter (%s) and finger count (%s)" %
                                (finger_size, num_fingers))

    def _select_single_finger_tips_by_size(self, finger_size, num_fingers, check_only):
        """
        Select single-finger tips matching the parameters. num_fingers should be 1 or 2.
        If check_only is True, don't actually select tips, but still raise exceptions as normal.
        """
        matching_tips = self.single_tips_by_size[finger_size]
        if not check_only:
            self.set_active_tip(matching_tips[0])
        if num_fingers == 2:
            if len(matching_tips) < 2:
                raise TipSelectionError("Not enough tips of the correct size")
            if not check_only:
                self.context.robot.change_tip(matching_tips[1].name, 1)
        elif num_fingers == 1:
            if not check_only:
                self.context.robot.detach_tip(1)
        else:
            raise TipSelectionError("Number of fingers must be 1 or 2")

    def select_tips_by_size(self, finger_size, num_fingers, check_only=False):
        """
        Select tips matching the parameters.
        If check_only is True, don't actually select tips, but still raise exceptions as normal.
        """
        if num_fingers >= 3:
            self._select_multi_finger_tip_by_size(finger_size, num_fingers, check_only)
        elif num_fingers >= 1:
            self._select_single_finger_tips_by_size(finger_size, num_fingers, check_only)
        else:
            raise TipSelectionError("Number of fingers must be set and positive")

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

