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
import json
from . import logger

try:
    import requests
except ImportError:
    raise ImportError("TnT Client requires Python module 'requests'. This module can be installed with command 'pip install requests' or from here: https://pypi.python.org/pypi/requests/")

log = logger.get_logger(__name__)


class RequestError(Exception):
    """ Error occurred during the request to the TnT Server """
    def __init__(self, status, message):
        self.status = status
        self.message = message
        Exception.__init__(self, message)

    def __str__(self):
        if self.message:
            return "{} - {}".format(self.status, self.message)


class TnTDutPoint(object):
    """ Point used for DUT operations """
    def __init__(self, x, y, z, tilt=None, azimuth=None):
        self.x = x
        self.y = y
        self.z = z
        self.tilt = tilt
        self.azimuth = azimuth

    def __repr__(self):
        return "x: %s; y: %s; z %s; tilt: %s; azimuth: %s" % \
            (self.x, self.y, self.z, self.tilt, self.azimuth)

    def to_dict(self):
        """
        Convert TnTDutPoint object to dictionary.
        :return: Dictionary with keys that correspond to class members.
        """
        params = {
            "x": self.x,
            "y": self.y,
            "z": self.z,
        }
        if self.tilt is not None:
            params["tilt"] = self.tilt
        if self.azimuth is not None:
            params["azimuth"] = self.azimuth

        return params


class TnTClientObject(object):
    """ This class provides (low level) access to TnT Server and its resources acting as a base class for all resources. """
    default_workspace = "ws"

    def __init__(self, host, port, workspace, resource_type=None, resource_name=None):
        global TnTRobotClient, TnTDUTClient, TnTTipClient, TnTCameraClient, TnTDutPhysicalButtonClient
        from .tnt_robot_client import TnTRobotClient
        from .tnt_dut_client import TnTDUTClient
        from .tnt_tip_client import TnTTipClient
        from .tnt_camera_client import TnTCameraClient
        from .tnt_dutphysicalbutton_client import TnTDutPhysicalButtonClient
        from .tnt_hsup_client import TnTHsupClient

        self._host = host
        self._port = port

        # Using sessions is faster than opening new connection every time sending request with request.get/post/put/delete
        self._session = requests.Session()
        self._resource_type = resource_type
        self._resource_name = resource_name

        if self._resource_type is not None and self._resource_type not in ["robot", "dut", "camera", "tip", "image",
                                                                           "detector", "dutphysicalbutton", "tool",
                                                                           "forcecalibrator", "analyzer"]:
            raise ValueError("Unrecognized resource type '{}'. \
            Supported values are: robot, dut, camera, tip, image, "
            "detector, dutphysicalbutton, tool, forcecalibrator, analyzer".format(resource_type))
        elif self._resource_type is not None:
            self._resource_type += "s"
        else:
            self._resource_type = None

        self._workspace = "http://{}:{}/tnt/workspaces/{}".format(host, port, workspace)

        if self._resource_type is not None:
            if self._resource_name:
                self._url = "http://{}:{}/tnt/workspaces/{}/{}/{}".format(host, port, workspace, self._resource_type, self._resource_name)
            else:
                self._url = "http://{}:{}/tnt/workspaces/{}/{}".format(host, port, workspace, self._resource_type)

        elif self._resource_name is not None:
            self._url = "http://{}:{}/tnt/workspaces/{}/{}".format(host, port, workspace, self._resource_name)

        else:
            self._url = "http://{}:{}/tnt/workspaces/{}".format(host, port, workspace)
        
    def __str__(self):
        if self._resource_name is None:
            return self._url
        else:
            return self._resource_name

    @property
    def host(self):
        """ Host IP address """
        return self._host

    @property
    def port(self):
        """ Host IP port """
        return self._port

    @property
    def resource_type(self):
        """ Resource type e.g. 'robot', 'dut', etc. """
        return self._resource_type

    @property
    def name(self):
        """ Resource name """
        return self._resource_name

    def _GET(self, target, parameters=None):
        return self._send_request("GET", target, parameters)

    def _POST(self, target, parameters):
        return self._send_request("POST", target, parameters)

    def _PUT(self, target, parameters):
        return self._send_request("PUT", target, parameters)

    def _DELETE(self, target, parameters):
        return self._send_request("DELETE", target, parameters)

    def _POST_ADVANCED(self, target, data=None, json=None, files=None):
        """
        allow to send json and data in request
        """
        url = '{base}/{t}'.format(base=self._url, t=target)
        # log.debug('post to {u}, data type {d}, json {j}'.format(u=url, d=type(data), j=json))
        response = self._session.post(url, data=data, json=json, files=files)
        log.debug('response {}'.format(str(response.content)))
        return self._get_response_content(response)

    def _send_request(self, method, target, parameters, base_url=None):
        """
        send request with content-type = application/json
        """
        # Sanity check for parameters
        if parameters is not None:
            if type(parameters) != dict:
                raise ValueError("Parameters must be provided in dictionary instead of " + str(type(parameters)))

        url = self._url if base_url is None else base_url

        if target is not None and len(target) > 0:
            url += "/" + target

        if method == "GET":
            if parameters is not None:
                url += "?"

                for key, value in parameters.items():
                    url += "{}={}&".format(key, value)

                # Remove trailing ampersand
                if url[-1] == "&":
                    url = url[:-1]

            response = self._session.get(url)

        elif method == "POST":
            response = self._session.post(url, data=json.dumps(parameters), headers={"content-type": "application/json"})

        elif method == "PUT":
            response = self._session.put(url, data=json.dumps(parameters), headers={"content-type": "application/json"})

        elif method == "DELETE":
            response = self._session.delete(url, data=json.dumps(parameters), headers={"content-type": "application/json"})

        else:
            raise ValueError("Unknown or unsupported HTTP method -- " + method)

        return self._get_response_content(response)

    def _get_response_content(self, response):
        """
        Return response content on success or raise RequestError
        :param response:
        :return:
        """
        # If request was completed successfully
        if 200 <= response.status_code < 300:

            if response.headers["Content-Type"] == "application/octet-stream":
                return response.content

            if response.headers["Content-Type"] == "image/jpeg":
                return response.content
                
            if response.headers["Content-Type"] == "image/png":
                return response.content

            content = self._decode_content(response.content)

            if response.headers["Content-Type"] == "application/json":
                return json.loads(content)

        else:
            content = self._decode_content(response.content)
                
            json_error = json.loads(content)
            log.debug('json {s} - {m}'.format(s=json_error["status"], m=json_error["message"]))
            raise RequestError(json_error["status"], json_error["message"])

    def _decode_content(self, content):
        """
        currently decode only if expecting json
        :param content: response.content
        :return:
        """
        if isinstance(content, bytes):
            content = content.decode()
        return content


class TnTClient(TnTClientObject):
    """ This class provides high level access to TnT Server and its resources.
    :example:
    client = TnTClient()

    robot = client.robot("MyRobotName")
    dut = client.dut("MyDutName")
    camera = client.camera("MyCameraName")

    robot.some_method()
    """
    def __init__(self, host="127.0.0.1", port=8000, workspace=TnTClientObject.default_workspace):
        self.workspace = workspace
        TnTClientObject.__init__(self, host, port, workspace=workspace)

    def robot(self, name):
        """
        Create a new robot client object with a given name.
        :param name: Name of robot to create client for.
        :return: TnTRobotClient object.
        """
        return TnTRobotClient(name, host=self.host, port=self.port, workspace=self.workspace)

    def robots(self):
        """
        Get a list of all available robots from TnT Server as robot clients.
        :return: List of TnTRobotClient objects corresponding to all robots in server.
        """
        robots = []

        for r in self._GET("robots")["robots"]:
            robots.append(self.robot(r["name"]))

        return robots

    def dut(self, name):
        """
        Create a new DUT client object with a given name.
        :param name: Name of DUT.
        :return: TnTDUTClient object corresponding to DUT with given name.
        """
        return TnTDUTClient(name, host=self.host, port=self.port, workspace=self.workspace)

    def duts(self):
        """
        Get a list of all available DUTs from TnT Server as DUT clients.
        :return: List of TnTDUTClient objects corresponding to all DUTs in server.
        """
        duts = []

        for d in self._GET("duts")["duts"]:
            duts.append(self.dut(d["name"]))

        return duts

    def tip(self, name):
        """
        Create a new tip client object with a given name.
        :param name: Name of tip.
        :return: TnTTipClient object corresponding to tip with given name.
        """
        return TnTTipClient(name, host=self.host, port=self.port, workspace=self.workspace)

    def tips(self):
        """
        Get a list of all available tips from TnT Server as tip clients.
        :return: List of TnTTipClient objects corresponding to all tips in server.
        """
        tips = []

        for t in self._GET("tips")["tips"]:
            tips.append(self.tip(t["name"]))

        return tips

    def camera(self, name):
        """
        Create a new camera client object with a given name.
        :param name: Name of camera.
        :return: TnTCameraClient object corresponding to camera with given name.
        """
        return TnTCameraClient(name, host=self.host, port=self.port, workspace=self.workspace)

    def cameras(self):
        """
        Get a list of all available cameras from TnT Server.
        :return: List of TnTCameraClient objects corresponding to all cameras in server.
        """
        cameras = []

        for i in self._GET("cameras")["cameras"]:
            cameras.append(self.camera(i["name"]))

        return cameras

    def dutphysicalbutton(self, name):
        """
        Create a new dutphysicalbutton client object with a given name.
        :param name: Name of DUT physical button.
        :return: TnTDutPhysicalButtonClient object corresponding to DUT physical button with given name.
        """
        return TnTDutPhysicalButtonClient(name, host=self.host, port=self.port, workspace=self.workspace)

    def dutphysicalbuttons(self):
        """
        Get a list of all available dutphysicalbuttons from TnT Server.
        :return: List of TnTDutPhysicalButtonClient objects corresponding to all DUT physical buttons in server.
        """
        dutphysicalbuttons = []

        for d in self._GET("dutphysicalbuttons")["dutphysicalbuttons"]:
            dutphysicalbuttons.append(self.dutphysicalbutton(d["name"]))

        return dutphysicalbuttons

    def version(self):
        """
        Get TnT Server version.
        :return: Version string.
        """
        base_url = "http://{}:{}/tnt".format(self._host, self._port)
        return self._send_request("GET", "version", parameters=None, base_url=base_url)["tnt_version"]