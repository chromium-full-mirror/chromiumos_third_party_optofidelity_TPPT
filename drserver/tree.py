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
from .node import Node, json_out
from .dut_server import DutServer
from .webdut_server import WebDutServer
from .gesture_images import *
import base64
import math


class TnTNode(Node):
    def __init__(self, name, poll_input=True):
        super().__init__(name)

        self.poll_input = poll_input

    @json_out
    def get_version(self):
        return {"tnt_version": "dry run"}


class DutNode(Node):
    def __init__(self, name):
        super().__init__(name)

        self._width = 0
        self._height = 0

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = value

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = value

    @property
    def top_left(self):
        return {"x": 0, "y": 0, "z": 0}

    @property
    def top_right(self):
        return {"x": 0, "y": 0, "z": 0}

    @property
    def bottom_left(self):
        return {"x": self.width, "y": self.height, "z": 0}

    @property
    def orientation(self):
        return 0

    @property
    def base_distance(self):
        return 10

    @json_out
    def get_svg_data(self):
        return ""

    @json_out
    def put_show_image(self, image):
        if image is not None and len(image) > 0:
            image = base64.decodebytes(image.encode("ascii"))
        else:
            image = None

        self.show_image(image)

        return "ok"

    @property
    def dut_server(self):
        return Node.find("dutserver")

    @property
    def webdut_server(self):
        return Node.find("webdutserver")

    def show_image(self, image):
        """
        Draws image to dut screen
        :param image: image as numpy array, bytes, or filename
        :param client_name: name of the communication client connected to DutServer or None (connect to first on list)

        """
        success = False
        if self.dut_server is not None:
            try:
                self.dut_server.show_image(self, image)
                success = True
            except Exception as e:
                pass

        if self.webdut_server is not None:
            try:
                self.webdut_server.show_image(self, image)
                success = True
            except Exception as e:
                pass

        if not success:
            print("dut server could not show image")

    @property
    def width_px(self):
        try:
            return self.dut_server.info(self.name)["display_resolution"]["width"]
        except:
            pass

        try:
            return self.webdut_server.info(self.name)["display_resolution"]["width"]
        except:
            pass
        return 0

    @property
    def height_px(self):
        try:
            return self.dut_server.info(self.name)["display_resolution"]["height"]
        except:
            pass

        try:
            return self.webdut_server.info(self.name)["display_resolution"]["height"]
        except:
            pass
        return 0

class TipNode(Node):
    def __init__(self, name):
        super().__init__(name)

        self._num_tips = 1
        self._tip_distance = 0
        self._first_finger_offset = 0
        self._separation = 0
        self._model = "Standard"

    @property
    def type(self):
        return "Tip"

    @property
    def model(self):
        return self._model

    @property
    def length(self):
        return 16

    @property
    def dimension(self):
        return {"x": 0, "y": 0, "z": self.length}

    @property
    def diameter(self):
        return 9

    @property
    def separation(self):
        return self._separation

    @property
    def num_tips(self):
        return self._num_tips

    @property
    def tip_distance(self):
        return self._tip_distance

    @property
    def first_finger_offset(self):
        return self._first_finger_offset

    @property
    def slot_in(self):
        return None

    @property
    def slot_out(self):
        return None


class RobotNode(Node):
    def __init__(self, name):
        super().__init__(name)

        self._finger_separation = 10.0
        self._speed = 50.0
        self._acceleration = 50.0
        self._tips = ["tip1", None]

    @json_out
    def get_active_finger(self):
        return 0

    @json_out
    def put_active_finger(self, finger_id):
        pass

    @json_out
    def put_speed(self, speed, acceleration):
        self._speed = speed
        self._acceleration = acceleration

    @json_out
    def get_speed(self):
        return {"speed": self._speed, "acceleration": self._acceleration}

    @json_out
    def put_detach_tip(self, tool_name=None, finger_id=None):
        self._tips[finger_id] = None

    @json_out
    def put_position(self, x, y, z, context, **kwargs):
        # dut.move() is used in jitter test but it is also used in transition movements.
        # Use some heuristics here to determine if user should touch the DUT.
        if context not in ["tnt", "ws"] and z <=0:
            print("Touch and hold at {:2f}, {:2f}".format(x, y))

            dut = Node.find(context)

            image = create_dut_tap_image(dut, x, y)

            dut.show_image(image)

            if Node.root.poll_input:
                input("Press enter to continue...")

    @json_out
    def put_change_tip(self, tip_id: str, tool_name=None, finger_id=None):
        if finger_id is None:
            finger_id = 0
        self._tips[finger_id] = tip_id

    @json_out
    def put_finger_separation(self, distance):
        self._finger_separation = distance
        return {"status": "ok"}

    @json_out
    def get_finger_separation(self):
        return self._finger_separation

    def tip(self, finger_id):
        if self._tips[finger_id] is None:
            return None

        return Node.find(self._tips[finger_id])


class GesturesNode(Node):
    def __init__(self, name):
        super().__init__(name)

    @json_out
    def put_jump(self, x: float, y: float, z: float = 0, jump_height: float = None):
        pass

    @json_out
    def put_tap(self, x: float, y: float, z: float = None, tilt: float = 0, azimuth: float = 0,
                clearance: float = 0, duration: float = 0):
        print("Tap at {:2f}, {:2f}".format(x, y))

        dut = self.parent

        dir_x = math.cos(math.radians(azimuth))
        dir_y = -math.sin(math.radians(azimuth))

        tip = Node.find("Robot1").tip(0)

        image = create_dut_tap_image(dut, x, y, dir_x, dir_y, tip.tip_distance, tip.num_tips)

        dut.show_image(image)

        if Node.root.poll_input:
            input("Press enter to continue...")

    @json_out
    def put_swipe(self, x1: float, y1: float, x2: float, y2: float, tilt1: float = 0, tilt2: float = 0,
                  azimuth1: float = 0, azimuth2: float = 0, clearance: float = 0, radius: float = 6):
        print("Swipe from {:2f}, {:2f} to {:2f}, {:2f}".format(x1, y1, x2, y2))

        dut = self.parent

        # Assume that azimuth1 == azimuth2. This is valid for 2-finger-dt robot.
        dir_x = math.cos(math.radians(azimuth1))
        dir_y = -math.sin(math.radians(azimuth1))

        tip = Node.find("Robot1").tip(0)

        image = create_dut_swipe_image(dut, x1, y1, x2, y2, dir_x, dir_y, tip.tip_distance, tip.num_tips)

        dut.show_image(image)

        if Node.root.poll_input:
            input("Press enter to continue...")


def create_dry_run_tree(config, poll_input=True, dut_comm=True):
    """
    Create node tree for the dry run environment.
    """
    tnt = TnTNode("tnt", poll_input)

    Node.root = tnt

    workspaces = Node("workspaces")

    tnt.add_child(workspaces)

    ws = Node("ws")

    workspaces.add_child(ws)

    duts = Node("duts")

    ws.add_child(duts)

    for dut_name, dut_config in config["duts"].items():
        dut = DutNode(dut_name)

        dut.width = dut_config["width"]
        dut.height = dut_config["height"]

        duts.add_child(dut)

        gestures = GesturesNode("gestures")

        dut.add_child(gestures)

    tips = Node("tips")

    ws.add_child(tips)

    for tip_name, tip_config in config["tips"].items():
        tip = TipNode(tip_name)

        tip._model = tip_config.get("model", "Standard")
        tip._num_tips = tip_config.get("num_tips", 1)
        tip._tip_distance = tip_config.get("tip_distance", 0)
        tip._first_finger_offset = tip_config.get("first_finger_offset", 0)
        tip._separation = tip_config.get("separation", 0)

        tips.add_child(tip)

    robots = Node("robots")
    ws.add_child(robots)

    robots.add_child(RobotNode("Robot1"))

    if dut_comm:
        dut_server = DutServer("dutserver")
        tnt.add_child(dut_server)

        webdut_server = WebDutServer("webdutserver")
        tnt.add_child(webdut_server)

        dut_server._init(host="0.0.0.0", port=50008)

        # Remember to set port 50009 in Chrome Extension settings.
        webdut_server._init(host="0.0.0.0", port=50009)

