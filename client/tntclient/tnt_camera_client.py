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
from .tnt_client import TnTClientObject, RequestError


class TnTCameraClient(TnTClientObject):
    """ This class implements methods to control TnT Server camera resources. """
    def __init__(self, name, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        TnTClientObject.__init__(self, host, port, workspace, 'camera', name)

    def open(self):
        """
        Open camera for use.
        After the camera has been opened, sequential images can be taken quickly.
        """

        self._PUT("/open", {})

    def close(self):
        """
        Shuts down the camera.
        """

        self._PUT("/close", {})

    def take_still(self, filetype="jpg", width=None, height=None, zoom=None, undistorted=False, exposure=None, gain=None):
        """
        Takes a photo. This function opens camera automatically, no need to use open() -function.
        :param filetype: jpg, png, raw(np.array)
        :param width: Target image width (optional).
        :param height: Target image height (optional)..
        :param zoom: Image zoom factor (optional).
        :param undistorted: true/false, only available after undistort called successfully (optional).
        :param exposure: Exposure in seconds (optional). If not set, uses last exposure used.
        :param gain: Gain value (optional). If not set, uses last gain value used.
        :return: Image in 'filetype' format.
        """

        params = {
            "filetype": filetype,
            "undistorted": undistorted
        }

        if width is not None:
            params["width"] = width

        if height is not None:
            params["height"] = height

        if zoom is not None:
            params["zoom"] = zoom

        if exposure is not None:
            params["exposure"] = exposure

        if gain is not None:
            params["gain"] = gain

        data = self._GET("still", params)

        if filetype == "bytes":
            w = int.from_bytes(data[0:4], byteorder="big")
            h = int.from_bytes(data[4:8], byteorder="big")
            d = int.from_bytes(data[8:12], byteorder="big")
            data = np.frombuffer(data[12:], dtype=np.uint8).reshape((h, w, d))

        return data

    def detect_icon(self, icon: str, confidence=0.75, context: str = "tnt", **kwargs):
        """
        List of detected objects with their positions in relation to given context.
        :param icon: Name of the icon. You can teach new icons with TnT UI.
        :param confidence: Confidence factor 0..1 where 1 is very confident. Normal confidence is about 0.7.
        :param context: Returned positions are relative to this context.
        :param kwargs: Additional parameters passed to camera, e.g. exposure, gain.
        :return: List of detected objects.
        """
        params = {
            "icon": icon,
            "confidence": confidence,
            "context": context
        }
        params.update(**kwargs)
        return self._GET("detect_icon", params)

    def read_text(self, context: str = "tnt", language: str = 'English', **kwargs):
        """
        Take a photo and analyze the image for text.
        :param context: Returned positions are relative to this context.
        :param language: Default is 'English'.
        :param kwargs: Parameters passed to camera, like exposure, gain, (bool)threshold, (bool)negate.
        :return: Found text with position information
        """
        params = {
            "language": language,
            "context": context
        }
        params.update(**kwargs)
        return self._GET("read_text", params)

    def move(self, x, y, z, context: str = "tnt"):
        """
        Move camera focus point to given position (x, y, and z-coordinate) in a given context.
        :param x: Target x coordinate in a given context.
        :param y: Target y coordinate in a given context.
        :param z: Target z coordinate in a given context.
        :param context: Name of the target context.
        """
        f = [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]
        params = {
            "frame": f,
            "context": context
        }
        self._PUT("move_with_robot", params)
