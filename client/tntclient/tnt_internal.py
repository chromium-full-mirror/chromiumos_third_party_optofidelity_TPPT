"""
    For OptoFidelity internal use only.


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

from tntclient.tnt_client import TnTClientObject
import tntclient.logger as logger
from tntclient.tnt_dut_client import TnTDUTClient
from tntclient.tnt_robot_client import TnTRobotClient

log = logger.get_logger(__name__)


class TnTInternalDetectorClient(TnTClientObject):
    """This class implements methods to control TnT Server detector resources."""
    def __init__(self, name, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        TnTClientObject.__init__(self, host, port, workspace, 'detector', name)

    def detect_icon(self, icon, image):
        """
        Tries to detect an icon from the given image and returns positions of the matching icons.

        :param icon: Bytes or file-like object (might accept dictionary).
        :param image: <type 'int'> resource_id of image on which detection should be performed.
        :return: Result from icon detector.
        """
        return self._POST_ADVANCED('detection/{img}'.format(img=image), files={'icon': icon})


class TnTInternalDutClient(TnTDUTClient):
    def __init__(self, name, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        super().__init__(name, workspace, host, port)

    def multiswipe(self, x1, y1, x2, y2, z=None, tilt=None, azimuth=None, clearance=0, n=2):
        """
        Performs multiple swipe movements in DUT context.

        :param x1: Start x coordinate on DUT.
        :param y1: Start y coordinate on DUT.
        :param x2: End x coordinate on DUT.
        :param y2: End y coordinate on DUT.
        :param z: Target z coordinate on DUT when hovering before and after gesture (default: DUT's base_distance).
        :param tilt: Tilt angle in DUT frame (default: 0).
        :param azimuth: Azimuth angle in DUT frame (default: 0).
        :param clearance: Z coordinate on DUT when running swipe (default: 0).
        :param n: Number of swipes to draw. Back and forth counts as two. (default: 2)
        """
        params = {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "n": n,
            "clearance": clearance,
        }

        if z is not None:
            params["z"] = z
        if tilt is not None:
            params["tilt"] = tilt
        if azimuth is not None:
            params["azimuth"] = azimuth

        self._PUT("gestures/multiswipe", params)

    def scan(self, x1, y1, x2, y2, z=None):
        """
        Performs scan gesture in DUT context.

        :param x1: Start x coordinate on DUT.
        :param y1: Start y coordinate on DUT.
        :param x2: End x coordinate on DUT.
        :param y2: End y coordinate on DUT.
        :param z: Target z coordinate on DUT when hovering before and after gesture (default: DUT's base_distance).
        """
        params = {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "z": z
        }

        self._PUT("gestures/scan", params)

    def map_to(self, x, y, z, to_context):
        """ Map given DUT coordinates into the specified context.

        :param x: X coordinate on DUT.
        :param y: Y coordinate on DUT.
        :param z: Z coordinate on DUT.
        :param to_context: To which context to map given DUT coordinates.
        :return: Dictionary of mapped coordinates with keys 'x', 'y', 'z', 'x_roll', 'y_roll', 'z_roll'.
        """
        params = {
            "x": x,
            "y": y,
            "z": z,
            "to_context": to_context,
        }

        return self._GET("map_to", params)

class TnTInternalRobotClient(TnTRobotClient):
    def __init__(self, name, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        super().__init__(name, workspace, host, port)

    def get_axis_parameter(self, axis: str, parameter: str):
        """
        Get SimpleMotion axis parameter with given axis name, parameter name.
        :param axis: Name of the SimpleMotion axis.
        :param parameter: Name of the SimpleMotion parameter.
        :return: Integer value.
        """
        p = {"axis": axis, "parameter": parameter}
        return self._GET("axis_parameter", p)

    def set_axis_parameter(self, axis: str, parameter: str, value: int):
        """
        Set SimpleMotion axis parameter with given axis name, parameter name.
        :param axis: Name of the SimpleMotion axis.
        :param parameter: Name of the SimpleMotion parameter.
        :param value: Integer value to set.
        :return: "ok" / error
        """
        p = {"axis": axis, "parameter": parameter, "value": value}
        return self._PUT("axis_parameter", p)

    def get_axis_position(self, axis: str):
        """
        Get single axis position on robot.
        'axis' is only for current robot's extra axes available in kinematics' RobotPosition, for example:
            - separation
            - voicecoil1
            - voicecoil2

        :param axis: Name of the axis.
        :return: Axis position value.
        """
        p = {"axis": axis}
        return self._GET("axis_position", p)

    def set_axis_position(self, axis: str, value):
        """
        Set single axis position on robot.
        Uses current robot speed, acceleration.
        'axis' is only for current robot's extra axes available in kinematics' RobotPosition, for example:
            - separation
            - voicecoil1
            - voicecoil2

        :param axis: Name of the axis.
        :param value: Axis position value
        :return: "ok" / error
        """
        p = {"axis": axis, "value": value}
        return self._PUT("axis_position", p)
