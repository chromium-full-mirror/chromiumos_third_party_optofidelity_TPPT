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
from operator import add, sub
from .tnt_client import TnTClient, TnTClientObject, RequestError, TnTDutPoint
from .tnt_robot_client import TnTRobotClient
from . import logger
import base64


log = logger.get_logger(__name__)


class TnTDUTClient(TnTClientObject):
    """ This class implements methods to control TnT Server DUT resources. """
    def __init__(self, name, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        TnTClientObject.__init__(self, host, port, workspace, 'dut', name)

        self._data = None
        self._parsed_data = None

        try:
            self._refresh_data()
        except RequestError as err:
            raise RuntimeError("Could not initialize DUT client: " + str(err))

        self._robot = None

    def _get_dut_data(self, name):
        self._refresh_data()
        return self._parsed_data[name]

    def _refresh_data(self):
        """
        Updates DUT information from the server.
        """
        self._data = self._GET("")["properties"]

        self._parsed_data = {}
        self._parsed_data["width"] = self._data["width"]
        self._parsed_data["height"] = self._data["height"]

        tl = self._data["top_left"]
        tr = self._data["top_right"]
        bl = self._data["bottom_left"]

        tl = [tl["x"], tl["y"], tl["z"]]
        tr = [tr["x"], tr["y"], tr["z"]]
        bl = [bl["x"], bl["y"], bl["z"]]

        # Because there's no point to implement full vector class at this time:
        tl_tr = map(sub, tr, tl)
        tl_bl = map(sub, bl, tl)
        br = map(add, tl, tl_tr)
        br = map(add, br, tl_bl)

        self._parsed_data["position"] = {
            "top_left": tl,
            "top_right": tr,
            "bottom_left": bl,
            "bottom_right": br,
        }

        self._parsed_data["top_left"] = tl
        self._parsed_data["top_right"] = tr
        self._parsed_data["bottom_left"] = bl
        self._parsed_data["bottom_right"] = br

        self._parsed_data["orientation"] = self._data["orientation"]

        self._parsed_data["base_distance"] = self._data["base_distance"]

    @property
    def width(self):
        """ Width of a DUT (X axis). """
        return self._get_dut_data("width")

    @property
    def height(self):
        """ Height of a DUT (Y axis). """
        return self._get_dut_data("height")

    @property
    def position(self):
        """
        Corner positions of the DUT in its relative coordinate system context.
        Property is in dictionary from {"top_left": top_left, "top_right": top_right,
        "bottom_left": bottom_left, "bottom_right": bottom_right}.
        """
        return self._get_dut_data("position")

    @property
    def top_left(self):
        """ Position of top left corner of the DUT. """
        return self._get_dut_data("top_left")

    @property
    def top_right(self):
        """ Position of top right corner of the DUT. """
        return self._get_dut_data("top_right")

    @property
    def bottom_left(self):
        """ Position of bottom left corner of the DUT. """
        return self._get_dut_data("bottom_left")

    @property
    def bottom_right(self):
        """ Position of bottom right corner of the DUT. """
        return self._get_dut_data("bottom_right")

    @property
    def tl(self):
        """ Shortcut for top_left. """
        return self.top_left

    @property
    def tr(self):
        """ Shortcut for top_right. """
        return self.top_right

    @property
    def bl(self):
        """ Shortcut for bottom_left. """
        return self.bottom_left

    @property
    def br(self):
        """ Shortcut for bottom_right. """
        return self.bottom_right

    @property
    def orientation(self):
        """
        Orientation of the DUT i.e. the basis vectors of DUT's transform matrix.
        Given as dictionary {'i': x_basis_vector, 'j': y_basis_vector, 'k': z_basis_vector}.
        """
        return self._get_dut_data("orientation")

    @property
    def robot(self):
        """ Returns robot object which DUT is using for position queries and some movements. """
        if self._robot is None:
            raise ValueError("Active robot object not set.")

        return self._robot

    @robot.setter
    def robot(self, value):
        """ Sets robot object which DUT should use for position queries and some movements. """
        if not isinstance(value, TnTRobotClient):
            raise ValueError("Robot object must be of type TnTRobotClient.")

        self._robot = value

    @property
    def base_distance(self):
        """
        DUT base distance.
        """
        return self._get_dut_data("base_distance")

    def get_robot_position(self):
        """
        Get the current robot position in DUT coordinates.
        :return: Robot position in DUT coordinates.
        """
        if self._robot is None:
            raise ValueError("Active robot object not set.")

        return self._robot.get_position(self.name)

    def jump(self, x, y, z, jump_height=None):
        """
        Performs a jump with given parameters.
        In case jump_height is not given, robot jumps to maximum height along robot z axis.

        :param x: Target x coordinate on DUT.
        :param y: Target y coordinate on DUT.
        :param z: Target z coordinate on DUT.
        :param jump_height: Height of the jump from DUT surface along DUT z-direction (default: jump to robot maximum height).
        """

        if x is None or y is None or z is None:
            raise ValueError("Parameters x, y, and z must be provided.")

        params = {
            "x": x,
            "y": y,
            "z": z
        }

        if jump_height is not None:
            params["jump_height"] = jump_height

        self._PUT("gestures/jump", params)

    def move(self, x, y, z, tilt=None, azimuth=None):
        """
        Moves in to given DUT position via straight path.

        :param x: Target x coordinate on DUT.
        :param y: Target y coordinate on DUT.
        :param z: Target z coordinate on DUT.
        :param tilt: Tilt angle in DUT frame (default: 0).
        :param azimuth: Azimuth angle in DUT frame (default: 0).
        """

        if self._robot is None:
            raise ValueError("Active robot object not set.")

        self._robot.move(x=x, y=y, z=z, tilt=tilt, azimuth=azimuth, context=self.name)

    def path(self, points):
        """
        Moves through a path defined by given points in DUT context

        :param points: List of TnTDutPoint objects that define points / poses in DUT context.
        """

        params = {"poses": [p.to_dict() for p in points]}

        self._PUT("gestures/path", params)

    def swipe(self, x1, y1, x2, y2, tilt1=None, tilt2=None, azimuth1=None, azimuth2=None, clearance=0, radius=6):
        """
        Performs swipe gesture in DUT context.
        Robot accelerates and decelerates along an arc of given radius before and after touching the DUT.

        :param x1: Start x coordinate on DUT.
        :param y1: Start y coordinate on DUT.
        :param x2: End x coordinate on DUT.
        :param y2: End y coordinate on DUT.
        :param tilt1: Start tilt angle in DUT frame.
        :param tilt2: End tilt angle in DUT frame.
        :param azimuth1: Start azimuth angle in DUT frame.
        :param azimuth2: End azimuth angle in DUT frame.
        :param clearance: Z coordinate on DUT when running swipe (default: 0).
        :param radius: Swipe acceleration arc radius.
        """
        params = {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "clearance": clearance,
            "radius": radius
        }

        if tilt1 is not None:
            params["tilt1"] = tilt1
        if azimuth1 is not None:
            params["azimuth1"] = azimuth1
        if tilt2 is not None:
            params["tilt2"] = tilt2
        if azimuth2 is not None:
            params["azimuth2"] = azimuth2

        self._PUT("gestures/swipe", params)

    def drag(self, x1, y1, x2, y2, z=None, tilt1=None, tilt2=None, azimuth1=None, azimuth2=None, clearance=0,
             predelay=0, postdelay=0):
        """
        Performs a drag gesture in DUT context.

        :param x1: Start x coordinate on DUT.
        :param y1: Start y coordinate on DUT.
        :param x2: End x coordinate on DUT.
        :param y2: End y coordinate on DUT.
        :param z: Target z coordinate on DUT when hovering before and after gesture (default: DUT's base_distance).
        :param tilt1: Start tilt angle in DUT frame.
        :param tilt2: End tilt angle in DUT frame.
        :param azimuth1: Start azimuth angle in DUT frame.
        :param azimuth2: End azimuth angle in DUT frame.
        :param clearance: Z coordinate on DUT when running drag (default: 0).
        :param predelay: Delay between touchdown and move in seconds.
        :param postdelay: Delay between the end of movement and touchup in seconds.
        """
        params = {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "clearance": clearance,
            "predelay": predelay,
            "postdelay": postdelay
        }

        if z is not None:
            params["z"] = z
        if tilt1 is not None:
            params["tilt1"] = tilt1
        if azimuth1 is not None:
            params["azimuth1"] = azimuth1
        if tilt2 is not None:
            params["tilt2"] = tilt2
        if azimuth2 is not None:
            params["azimuth2"] = azimuth2

        send = self._PUT

        send("gestures/drag", params)

    def drag_force(self, x1, y1, x2, y2, force, z=None, tilt1=None, tilt2=None, azimuth1=None, azimuth2=None):
        """
        Performs a drag gesture with force in DUT context.

        :param x1: Start x coordinate on DUT.
        :param y1: Start y coordinate on DUT.
        :param x2: End x coordinate on DUT.
        :param y2: End y coordinate on DUT.
        :param force: Grams of force to apply when running on DUT surface.
        :param z: Target z coordinate on DUT when hovering before and after gesture (default: DUT's base_distance).
        :param tilt1: Start tilt angle in DUT frame.
        :param tilt2: End tilt angle in DUT frame.
        :param azimuth1: Start azimuth angle in DUT frame.
        :param azimuth2: End azimuth angle in DUT frame.
        """
        params = {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "force": force
        }

        if z is not None:
            params["z"] = z
        if tilt1 is not None:
            params["tilt1"] = tilt1
        if azimuth1 is not None:
            params["azimuth1"] = azimuth1
        if tilt2 is not None:
            params["tilt2"] = tilt2
        if azimuth2 is not None:
            params["azimuth2"] = azimuth2

        send = self._PUT

        send("gestures/drag_force", params)

    def tap(self, x, y, z=None, tilt=None, azimuth=None, clearance=0, duration=None):
        """
        Performs a tap gesture in DUT context.

        :param x: Target x coordinate on DUT.
        :param y: Target y coordinate on DUT.
        :param z: Target z coordinate on DUT when hovering before and after gesture (default: DUT's base_distance).
        :param tilt: Tilt angle in DUT frame (default: 0).
        :param azimuth: Azimuth angle in DUT frame (default: 0).
        :param clearance: Z coordinate on DUT on tap down (default: 0).
        :param duration: How long to keep finger down in seconds (default: 0s).
        """
        params = {
            "x": x,
            "y": y,
            "clearance": clearance
        }

        if z is not None:
            params["z"] = z
        if duration is not None:
            params["duration"] = duration
        if tilt is not None:
            params["tilt"] = tilt
        if azimuth is not None:
            params["azimuth"] = azimuth

        self._PUT("gestures/tap", params)

    def watchdog_tap(self, x: float, y: float, z: float = None, tilt: float = 0, azimuth: float = 0,
                clearance: float = 0, duration: float = 0):
        """
        Performs a tap designed for Watchdog measurement with given parameters.

        :param x: Target x coordinate on DUT.
        :param y: Target y coordinate on DUT.
        :param z: Target z coordinate on DUT when hovering before and after gesture (default: DUT's base_distance).
        :param tilt: Tilt angle in DUT frame (default: 0).
        :param azimuth: Azimuth angle in DUT frame (default: 0).
        :param clearance: (optional) distance from DUT surface during movement
        :param duration: How long to keep finger down in seconds (default: 0s).
        :return: "ok" / error
        """

        params = {
            "x": x,
            "y": y,
            "tilt": tilt,
            "azimuth": azimuth,
            "clearance": clearance,
            "duration": duration
        }

        if z is not None:
            params["z"] = z

        self._PUT("gestures/watchdog_tap", params)

    def double_tap(self, x, y, z=None, tilt=None, azimuth=None, clearance=0, duration=None, interval=None):
        """
        Performs a double tap gesture in DUT context.

        :param x: Target x coordinate on DUT.
        :param y: Target y coordinate on DUT.
        :param z: Target z coordinate on DUT when hovering before and after gesture (default: DUT's base_distance).
        :param tilt: Tilt angle in DUT frame (default: 0).
        :param azimuth: Azimuth angle in DUT frame (default: 0).
        :param clearance: Z coordinate on DUT on tap down (default: 0).
        :param duration: How long to keep finger down in seconds (default: 0s).
        :param interval: How long to wait between taps (default: 0s).
        """
        params = {
            "x": x,
            "y": y,
            "clearance": clearance
        }

        if z is not None:
            params["z"] = z
        if tilt is not None:
            params["tilt"] = tilt
        if azimuth is not None:
            params["azimuth"] = azimuth
        if duration is not None:
            params["duration"] = duration
        if interval is not None:
            params["interval"] = interval

        self._PUT("gestures/double_tap", params)

    def multi_tap(self, points, lift=2, clearance=0):
        """
        Performs multiple tap gestures in DUT context according to given points.
        Start and end of multi-tap sequence is the base distance of the DUT.

        :param points: List of TnTDUTPoint objects indicating where to tap. Z coordinates of the points
                       are ignored and lift and clearance are used for tap movement.
        :param lift: Distance of how high the effector is raised from the DUT between the taps.
        :param clearance: Z coordinate on DUT on tap down (default: 0).
        """

        # Make one path

        poselist = [{
            "x": points[0].x,
            "y": points[0].y,
            "z": self.base_distance     # safe approach height
        }]

        for p in points:
            poselist += [{
                "x": p.x,
                "y": p.y,
                "z": lift
            },{
                "x": p.x,
                "y": p.y,
                "z": clearance
            },{
                "x": p.x,
                "y": p.y,
                "z": lift,
            }]

        poselist += [{
            "x": points[-1].x,
            "y": points[-1].y,
            "z": self.base_distance  # safe height
        }]

        params = {
            "poses": poselist
        }

        self._PUT("gestures/path", params)

    def press(self, x, y, force, z=None, tilt=None, azimuth=None, duration=None, press_depth=-1):
        """
        Performs a press gesture in DUT context.

        :param x: Target x coordinate on DUT.
        :param y: Target y coordinate on DUT.
        :param force: Force in grams, to be activated after moving to lower position.
        :param z: Target z coordinate on DUT when hovering before and after gesture (default: DUT's base_distance).
        :param tilt: Tilt angle in DUT frame (default: 0).
        :param azimuth: Azimuth angle in DUT frame (default: 0).
        :param duration: How long to keep specified force active in seconds (default: 0s).
        :param press_depth: Distance from DUT surface during press, negative values being below/through DUT surface.
        Tip will be pressed to the desired depth if the force limit is not reached before that.
        If the force limit is reached before desired depth, the movement will stop there. (default: -1mm).
        """
        params = {
            "x": x,
            "y": y,
            "z": z,
        }

        if tilt is not None:
            params["tilt"] = tilt
        if azimuth is not None:
            params["azimuth"] = azimuth
        if force is not None:
            params["force"] = force
        if duration is not None:
            params["duration"] = duration
        if press_depth is not None:
            params['press_depth'] = press_depth

        self._PUT("gestures/press", params)

    def circle(self, x, y, r, n=1, angle=0, z=None, tilt=None, azimuth=None, clearance=0, clockwise=False):
        """
        Performs a circle gesture in DUT context.

        :param x: Circle center x coordinate on DUT.
        :param y: Circle center y coordinate on DUT.
        :param r: Circle radius.
        :param n: Number of revolutions. Floats can be used.
        :param angle: Start circle angle in degrees. For 0 angle, x is x0+r and y is y0.
        :param z: Target z coordinate on DUT when hovering before and after gesture (default: DUT's base_distance).
        :param tilt: Tilt angle in DUT frame (default: 0).
        :param azimuth: Azimuth angle in DUT frame (default: 0).
        :param clearance: Z coordinate on DUT when moving in circle (default: 0).
        :param clockwise: True to move clockwise, false to move counter clockwise.
        """
        params = {
            "x": x,
            "y": y,
            "r": r,
            "n": n,
            "angle": angle,
            "clearance": clearance,
            "clockwise": clockwise,
        }

        if z is not None:
            params["z"] = z
        if tilt is not None:
            params["tilt"] = tilt
        if azimuth is not None:
            params["azimuth"] = azimuth

        self._PUT("gestures/circle", params)

    def list_buttons(self):
        """
        List buttons of the current DUT.

        :return: List of TnTDutPhysicalButtonClient objects.
        """
        all_buttons = TnTClient(host=self.host, port=self.port, workspace=self.default_workspace).dutphysicalbuttons()

        child_buttons = []

        for button in all_buttons:
            if button.parent == self.name:
                child_buttons.append(button)

        return child_buttons

    def press_button(self, button_name):
        """
        Press DUT button.

        :param button_name: Name of button to press.
        """
        buttons = self.list_buttons()
        for button in buttons:
            if button.name == button_name:
                return button.press()

    def screenshot(self, camera_id="Camera1", **kwargs):
        """
        Capture screenshot.

        :param camera_id: Id of camera to use to take a screenshot.
        :param kwargs: extra parameters to pass to camera like exposure, gain
        :return: image name <str>
        """

        params = {
            "camera_id": camera_id
        }

        response = self._POST("screenshot", params)
        log.debug('screenshot response {}{d}'.format(response, d=dir(response)))
        if response and "name" in response.keys():
            return response["name"]
        else:
            return None

    def find_objects(self, filename, min_score=None, crop_left=None, crop_upper=None,
                     crop_right=None, crop_lower=None, crop_unit=None):
        """
        Find an object model (.shm) from the currently visible portion of the screen.

        :example:
        Response body:
                success -- Any matches found [True | False]
                screenshot -- Address of the screenshot
                results -- Array of Result objects

            Result object:
                score -- Match score [0.0 .. 1.0]
                topLeftX -- Bounding box top left x coordinate
                topLeftY -- Bounding box top left x coordinate
                bottomRightX -- Bounding box bottom right x coordinate
                bottomRightY -- Bounding box bottom right y coordinate
                centerX -- Bounding box center x coordinate
                centerY -- Bounding box center y coordinate
                shape -- Name of the shape file

        Example return value:
            {
                "success": True
                "screenshot": "localhost:8000/TnTAPI/Screenshots/1.jpg"
                "results":
                [{
                    "topLeftX": 4.21,
                    "topLeftY": 2.37,
                    "bottomRightX": 6.23,
                    "bottomRightY": 3.54,
                    "centerX": 5.22,
                    "centerY": 2.96,
                    "shape": "shapeName.shm",
                    "score": 0.781
                }]
            }

        :param filename: Name of file containing object model.
        :param min_score: Minimum accepted confidence score of result [0.0 .. 1.0] (optional).
        :param crop_left: Left coordinate for cropping rectangle.
        :param crop_upper: Upper coordinate for cropping rectangle.
        :param crop_right: Right coordinate for cropping rectangle.
        :param crop_lower: Lower coordinate for cropping rectangle.
        :param crop_unit: Unit of crop coordinates (per/mm/pix).
        :return: Dictionary with keys: "success", "screenshot", "results".

        Response body:
                success -- Any matches found [True | False]
                screenshot -- Address of the screenshot
                results -- Array of Result objects

            Result object:
                score -- Match score [0.0 .. 1.0]
                topLeftX -- Bounding box top left x coordinate
                topLeftY -- Bounding box top left x coordinate
                bottomRightX -- Bounding box bottom right x coordinate
                bottomRightY -- Bounding box bottom right y coordinate
                centerX -- Bounding box center x coordinate
                centerY -- Bounding box center y coordinate
                shape -- Name of the shape file

        Example return value:
            {
                "success": True
                "screenshot": "localhost:8000/TnTAPI/Screenshots/1.jpg"
                "results":
                [{
                    "topLeftX": 4.21,
                    "topLeftY": 2.37,
                    "bottomRightX": 6.23,
                    "bottomRightY": 3.54,
                    "centerX": 5.22,
                    "centerY": 2.96,
                    "shape": "shapeName.shm",
                    "score": 0.781
                }]
            }
        """

        params = {
            "filename": filename,
        }

        if min_score is not None:
            params["min_score"] = min_score
        if crop_left is not None:
            params["crop_left"] = crop_left
        if crop_right is not None:
            params["crop_right"] = crop_right
        if crop_upper is not None:
            params["crop_upper"] = crop_upper
        if crop_lower is not None:
            params["crop_lower"] = crop_lower
        if crop_unit is not None:
            params["crop_unit"] = crop_unit

        return self._POST("find_objects", params)

    def search_text(self, pattern, regexp=False, language='English', min_score=1.0, case_sensitive=True,
                    crop_left=None, crop_upper=None, crop_right=None, crop_lower=None, crop_unit=None):
        """
        Search text pattern from the visible portion of the DUT screen.

        :param pattern: Text or pattern to find. Search all by default.
        :param regexp: Use pattern as a regexp. [True | False (default)]
        :param language: OCR language. [English (default)|Finnish]
        :param min_score: Minimum score (confidence value). 0.0 - 1.0. Default is 1.0. Value over 0.6 means the sequences are close matches.
        :param case_sensitive: Should the comparision be done case sensitive or not. [True (default) | False].
        :param crop_left: Left coordinate for cropping rectangle.
        :param crop_right: Right coordinate for cropping rectangle.
        :param crop_upper: Upper coordinate for cropping rectangle.
        :param crop_lower: Lower coordinate for cropping rectangle.
        :param crop_unit: Unit of crop coordinates (per/mm/pix).
        :return: Dictionary with keys "success", and "results".

            Example return:
            {
                "success": True
                "results":
                [{
                    "topLeftX": 4.21,
                    "topLeftY": 2.37,
                    "bottomRightX": 6.23,
                    "bottomRightY": 3.54,
                    "centerX": 5.22,
                    "centerY": 2.96,
                    "score": 0.781
                }]
            }
        """

        params = {
            "pattern": pattern,
            "regexp": regexp,
            "language": language,
            "min_score": min_score,
            "case_sensitive": case_sensitive
        }

        if crop_left is not None:
            params["crop_left"] = crop_left
        if crop_right is not None:
            params["crop_right"] = crop_right
        if crop_upper is not None:
            params["crop_upper"] = crop_upper
        if crop_lower is not None:
            params["crop_lower"] = crop_lower
        if crop_unit is not None:
            params["crop_unit"] = crop_unit

        return self._POST("search_text", params)

    def show_image(self, image: bytes):
        """
        Show bytes image on DUT screen.
        :param image: Image as bytes. None will empty the screen
        :return: "ok" / error
        """
        if image is not None:
            data = base64.encodebytes(image).decode("ascii")
        else:
            data = ""
        return self._PUT("show_image", {"image": data})

    def info(self):
        """
        Get raw info dictionary from DUT.
        Contains information about DUT model, display resolution, etc.
        :return: dict
        """
        return self._GET("info")

    def touches(self):
        """
        Gets list of touches since last call of this function.
        If you want to clear the touches buffer, call this function and discard the results.

        Current Android application supports the following fields:
            x           Touch x-coordinate. Touch resolution is the same as screen pixel resolution.
            y           Touch y-coordinate. Touch resolution is the same as screen pixel resolution.
            pressure    Touch pressure, float value in range 0..1, device dependent and not any standard unit.
            id          Touch id. Sequential number where every new finger to touch the screen
                        takes the first free positive number as id.
            action      Numbered enumeration where:
                        0 = touch start
                        1 = touch end
                        2 = touch move / stays pressed at point
                        3 = touch cancelled
            orientation Stylus event; angle in radians where 0 == north, -pi/2 = west, pi/2 = east
            azimuth     Stylus event; angle in radians where 0 == normal to surface and M_PI/2 is flat to surface.
            distance    Stylus event; 0.0 indicates direct contact and larger values
                                      indicate increasing distance from the surface.

        :return: (dict) where key 'fields' is a list of touch field names.
                    and where key 'touches' is a list of touches. One touch is an array of values.
        """
        r = self._GET("touches")
        return r

    def filter_points(self, points, region, margin=0):
        """
        Filter a list of points that are inside of DUT shape, given region and margin.
        :param points: List of (x, y) points, millimeters.
        :param region: Name of the region.
        :param margin: Margin inwards the given region, millimeters.
        :return: Filtered list of (x, y) points.
        """
        p = {"points": points, "region_name": region, "margin": margin}
        r = self._PUT("filter_points", p)
        return r

    def filter_lines(self, lines, region, margin=0):
        """
        Filter list of (x1, y1, x2, y2) lines with given region and margin.
        The filter will cut lines to pieces that fit inside the region with given margin.
        One given line can result to none or several lines.
        :param lines: List of (x1, y1, x2, y2) lines, in millimeters.
        :param region: Name of the filter region.
        :param margin: Margin inwards the region, millimeters.
        :return: List of list of (x1, y1, x2, y2) lines (each given line results to a list of lines).
        """
        p = {"lines": lines, "region_name": region, "margin": margin}
        r = self._PUT("filter_lines", p)
        return r

    def region_contour(self, region, num_points):
        """
        Return the given region as a list of (x, y) points.
        "contour" as in how OpenCV names the approximation of a shape as a point list:
        'Contours can be explained simply as a curve joining all the continuous points (along the boundary)'
        Can be used to OpenCV shape analysis or any other shape-analysis or geometric operation.
        :param region: Name of the region.
        :param num_points: Number of points to use on contour.
        :return: List of (x, y) contour points, in millimeters.
        """
        r = self._GET("region_contour", {"region_name": region, "num_points": num_points})
        return r

    def svg_data(self):
        """
        Return the svg file specified for the dut. If there is
        no specified file, return empty string
        :return: svg file or empty string
        """
        r = self._GET("svg_data")
        return r


    """

    Google specific gestures

    """

    def pinch(self, x, y, d1, d2, azimuth, z=None, clearance=0):
        """
        Performs a pinch gesture in DUT context.

        :param x: Target x coordinate on DUT. Target is the middle position between fingers.
        :param y: Target y coordinate on DUT. Target is the middle position between fingers.
        :param d1: Distance between fingers at the beginning.
        :param d2: Distance between fingers at the end.
        :param azimuth: Azimuth angle during the pinch.
        :param z: Overrides base distance.
        :param clearance: Distance from DUT surface during gesture.
        """
        params = {
            "x": x,
            "y": y,
            "d1": d1,
            "d2": d2,
            "azimuth": azimuth,
            "clearance": clearance
        }
        if z is not None:
            params.update({"z": z})

        self._PUT("gestures/pinch", params)

    def drumroll(self, x, y, azimuth, separation, tap_count, tap_duration, clearance=0):
        """
        Taps tap_count times with two fingers, one finger at a time, starting with finger 1 (left finger).
        Tapping is done with given azimuth angle and finger separation.
        Tapping is done tap_duration seconds, to which period the tap_count number of taps is layed out evenly.

        :param x: Target x coordinate on DUT.
        :param y: Target y coordinate on DUT.
        :param azimuth: Azimuth angle during the gesture.
        :param separation: Separation between the fingers during the gesture, millimeters.
        :param tap_count: Number of taps to perform.
        :param tap_duration: Duration of all taps together, seconds.
        :param clearance: Distance from DUT surface during gesture.
        """
        params = {
            "x": x,
            "y": y,
            "azimuth": azimuth,
            "separation": separation,
            "tap_count": tap_count,
            "tap_duration": tap_duration,
            "clearance": clearance
            }

        self._PUT("gestures/drumroll", params)

    def compass(self, x, y, azimuth1, azimuth2, separation, z=None, clearance=0):
        """
        Compass movement.
        Primary finger (the left finger) stays at x, y position while the other finger rotates around it.
        Rotation starts at azimuth angle a1 and ends at azimuth angle a2.
        Rotation will be done to shortest route direction.

        :param x: Target x coordinate on DUT.
        :param y: Target y coordinate on DUT.
        :param azimuth1: Start azimuth angle.
        :param azimuth2: End azimuth angle.
        :param separation: Distance between fingers during the gesture
        :param z: Target z coordinate on DUT when hovering before and after gesture (default: DUT's base_distance).
        :param clearance: Distance from DUT surface during gesture.
        """
        params = {
            "x": x,
            "y": y,
            "azimuth1": azimuth1,
            "azimuth2": azimuth2,
            "separation": separation,
            "clearance": clearance
            }

        if z is not None:
            params.update({"z": z})

        self._PUT("gestures/compass", params)

    def compass_tap(self, x, y, azimuth1, azimuth2, separation, tap_azimuth_step, z=None,
                    tap_with_stationary_finger=False, clearance=0):
        """
        Compass movement with tapping.
        Primary finger (the left finger) stays at x, y position while the other finger rotates around it.
        Rotation starts at azimuth angle a1 and ends at azimuth angle a2.
        Rotation will be done to shortest route direction.
        Tapping is done with selected finger. (moving finger by default)

        :param x: Target x coordinate on DUT.
        :param y: Target y coordinate on DUT.
        :param azimuth1: Start azimuth angle.
        :param azimuth2: End azimuth angle.
        :param separation: Distance between fingers during the gesture.
        :param tap_azimuth_step: Angle in degrees between taps.
        :param z: Target z coordinate on DUT when hovering before and after gesture and in-between taps (default: DUT's base_distance).
        :param tap_with_stationary_finger: Stationary or moving finger does the tapping.
        :param clearance: Distance from DUT surface during gesture.
        """
        params = {
            "x": x,
            "y": y,
            "azimuth1": azimuth1,
            "azimuth2": azimuth2,
            "separation": separation,
            "tap_azimuth_step": tap_azimuth_step,
            "tap_with_stationary_finger": tap_with_stationary_finger,
            "clearance": clearance
            }

        if z is not None:
            params.update({"z": z})

        self._PUT("gestures/compass_tap", params)

    def touch_and_tap(self, touch_x: float, touch_y: float, tap_x: float, tap_y: float, z: float = None,
                      number_of_taps=1, tap_predelay=0, tap_duration=0, tap_interval=0, clearance: float=0):
        """
        Performs a gesture where primary finger is touching a location and secondary finger is doing a taping gesture
        at another location.
        You can define the x, y coordinates for both fingers separately.

        :param touch_x: Touching finger x, millimeters.
        :param touch_y: Touching finger y, millimeters.
        :param tap_x: Tapping finger x, millimeters.
        :param tap_y: Tapping finger y, millimeters.
        :param z: Target z coordinate on DUT when hovering before and after gesture and in-between taps (default: DUT's base_distance).
        :param number_of_taps: Number of taps to perform. 1 for single tap, 2 for double tap, ...
        :param tap_predelay: Duration to touch with primary finger before tapping with secondary finger.
        :param tap_duration: Time to wait during the tap finger down, seconds.
        :param tap_interval: Time interval between the taps, seconds. Only affects number_of_taps >= 2
        :param clearance: (optional) distance from DUT surface during movement
        :return: "ok" / error
        """
        params = {"touch_x": touch_x,
                  "touch_y": touch_y,
                  "tap_x": tap_x,
                  "tap_y": tap_y,
                  "number_of_taps": number_of_taps,
                  "tap_predelay": tap_predelay,
                  "tap_duration": tap_duration,
                  "tap_interval": tap_interval,
                  "clearance": clearance}
        if z is not None:
            params.update({"z": z})

        return self._PUT("gestures/touch_and_tap", params)

    def line_tap(self, x1: float, y1: float, x2: float, y2: float, tap_distances: list, separation: float=None,
                 azimuth: float=0, z: float=None, clearance: float=0):
        """
        Moves the robot along a line between x1, y1 and x2, y2 and taps the surface with primary finger
        at given distances relative to the x1, y1 starting position.

        :param x1: Line start x, millimeters.
        :param y1: Line start y, millimeters.
        :param x2: Line end x, millimeters.
        :param y2: Line end y, millimeters.
        :param tap_distances: Tap locations as in distances from the beginning of the line, millimeters.
        :param separation: Distance between finger centers, millimeters. If not defined then default distance is used.
        :param azimuth: Azimuth angle to use during the line.
        :param z: Target z coordinate on DUT when hovering before and after gesture and in-between taps.
                  (default: DUT's base_distance).
        :param clearance: (optional) Distance from DUT surface during movement.
        :return: "ok" / error
        """
        params = {"x1": x1,
                  "y1": y1,
                  "x2": x2,
                  "y2": y2,
                  "tap_distances": tap_distances,
                  "azimuth": azimuth,
                  "clearance": clearance}

        if separation is not None:
            params.update({"separation": separation})

        if z is not None:
            params.update({"z": z})

        return self._PUT("gestures/line_tap", params)
