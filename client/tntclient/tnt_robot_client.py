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
from .tnt_client import TnTClientObject
from .tnt_tip_client import TnTTipClient
from . import logger

log = logger.get_logger(__name__)


class TnTRobotClient(TnTClientObject):
    """
    This class implements TnT robot client to remote control TnT server.
    """
    def __init__(self, name, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        TnTClientObject.__init__(self, host, port, workspace, 'robot', name)

        self._speed = None

    def set_speed(self, speed=None, acceleration=None):
        """
        Set robot speed and acceleration.
        :param speed: Linear movement speed in mm/s.
        :param acceleration: Robot acceleration in mm/s^2.
        """
        params = {
            "speed": speed,
            "acceleration": acceleration,
        }

        self._PUT("speed", params)

    def get_speed(self):
        """
        Returns robot's current speed and acceleration.
        :return: Dictionary with keys 'speed' and 'acceleration'.
        """
        return self._GET("speed", {})

    def move(self, x, y, z, tilt=None, azimuth=None, context="tnt"):
        """
        Moves robot into a given location using a linear motion. Coordinates and angles are interpreted in given context.
        Values tilt and azimuth are taken from Euler angles for global static y and z axes (in selected context)
        that are applied in order y, z. Tilt is angle around y-axis and azimuth is negative angle around z-axis.
        :param x: Target x coordinate.
        :param y: Target y coordinate.
        :param z: Target z coordinate.
        :param tilt: Euler angle for static y-axis (default: 0) in selected context.
        :param azimuth: Negative Euler angle for static z-axis (default: 0) in selected context.
        :param context: Name of context where coordinates and angles are interpreted.
        """

        params = {
            "x": x,
            "y": y,
            "z": z,
            "context": context
        }

        if tilt is not None:
            params["tilt"] = tilt
        if azimuth is not None:
            params["azimuth"] = azimuth

        self._PUT("position", params)

    def change_tip(self, tip, finger_id=0):
        """
        Commands robot to change new tool tip from tip holder.
        :param tip: Name of tip to make the current tip.
        :param finger_id: ID of finger where to change tip to.
        """
        if isinstance(tip, TnTTipClient):
            tip = tip.name

        self._PUT("change_tip", { "tip_id": tip, "finger_id": finger_id })

    def detach_tip(self, finger_id=0):
        """
        Detach tip from robot finger if one is attached.
        :param finger_id: ID of finger.
        :return: Name of the tip that was detached.
        """
        return self._PUT("detach_tip", {"finger_id": finger_id})

    def get_position(self, context="tnt"):
        """
        Returns the current robot position in given context.
        :param context: Name of context where to evaluate the position.
        :return: Dictionary with keys 'position' and 'status'.
        """
        params = None

        if context is not None:
            params = { "context": context }

        result = self._GET("position", params)

        if 'head' in result:
            del result['head']
        if 'frame' in result:
            del result['frame']

        return result

    def go_home(self):
        """ Commands the robot to go into home position. """
        return self._PUT("home", {})

    def reset_robot_error(self):
        """ Resets robot error state. """
        self._PUT("reset_error", None)

    def set_finger_separation(self, distance):
        """
        Set separation of two fingers in mm. Separation distance is measured from finger axes.
        :param distance: Distance in mm.
        :return: Dictionary with "status" key.
        """
        return self._PUT("finger_separation", {"distance": distance})

    def get_finger_separation(self):
        """
        Get separation of two fingers in mm.
        :return: Separation distance in mm.
        """
        return self._GET("finger_separation")

    def set_active_finger(self, finger_id):
        """
        Set active finger.
        Kinematics are applied to the active finger so that it is possible
        to command either of the two fingers to specified pose.
        :param finger_id: ID of finger to set active. 0=axial finger, 1=separated finger.
        """
        self._PUT("active_finger", {"finger_id": finger_id})

    def get_active_finger(self):
        """
        Get active finger.
        :return: Active finger ID.
        """
        return self._GET("active_finger")
