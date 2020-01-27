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
from . import logger

log = logger.get_logger(__name__)


class TnTHsupClient(TnTClientObject):
    """
    This class implements TnT HSUP (Human Simulated User Performance) client.
    Initialize an instance of this class for the required analysis type (name) and then start measurement
    and analysis.

    NOTE: Do not create instances of this class but rather one of the subclasses.

    Here are examples on how analysis could be used.
    :example:

        # This example shows how to use analysis when it's stopped from the script after robot movement.
        from tntclient.tnt_hsup_client import TnTHsupP2IClient
        from tntclient.tnt_dut_client import TnTDUTClient

        analysis = TnTHsupP2IClient()
        analysis.start(settings_path=r"C:\p2i_config.yaml")
        dut.swipe(50, 10, 50, 100)
        analysis.stop()
        results = analysis.get_results()
        print("Analysis results: {}".format(results))

    :example:

        # This example shows how to use analysis when timeout is configured into YAML file
        # and that stops the measurement
        import time
        from tntclient.tnt_hsup_client import TnTHsupSpaClient

        analysis = TnTHsupSpaClient()
        analysis.start(settings_path=r"C:\spa_config.yaml")
        while True:
            status = analysis.get_status()
            print("Analysis status: {}".format(status))

            if status['status_analysis'] == 'stopped':
                break
            time.sleep(1)

        results = analysis.get_results()
        print("Analysis results: {}".format(results))
    """

    def __init__(self, name, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        """
        Constructor.
        :param name: Name of the analysis. One of 'watchdog', 'spa', 'p2i'
        :param workspace: Workspace name.
        :param host: IP address.
        :param port: Port number.
        """
        TnTClientObject.__init__(self, host, port, workspace, 'analyzer', name)

    def start(self, settings_path=None):
        """
        Start measurement and analysis with given settings.

        :param settings_path: Path of the setting file.
        :return: Nothing.
        """

        params = {
            "settings_path": settings_path
        }

        return self._PUT("start_measurement", params)

    def stop(self):
        """
        Stop measurement. Analysis processing might still continue.

        :return: Nothing.
        """

        params = {}
        return self._PUT("stop_measurement", params)

    def get_results(self):
        """
        Returns the results of the analysis.
        :return: HSUP analysis results.
        """
        return self._GET("results")

    def get_status(self):
        """
        Returns the status of the analysis.
        :return: Status information of the previously triggered analysis. Dict with the following fields:
                status_analysis: State of the analysis processing.
                status_results_storage: State of storing images modified by analysis to disk.
                status_input_storage: State of storing images taken with camera to disk.
                images_total: Total number of images captured.
                images_remaining: Number of images analyzed so far.
            States are either 'running' or 'stopped'
        """
        return self._GET("status")


class TnTHsupWatchdogClient(TnTHsupClient):
    """
    This class implements watchdog client.
    """
    def __init__(self, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        """
        Constructor.
        :param workspace: Workspace name.
        :param host: IP address.
        :param port: Port number.
        """
        super().__init__(name="watchdog", workspace=workspace, host=host, port=port)


class TnTHsupSpaClient(TnTHsupClient):
    """
    This class implements scrolling performance analysis (SPA) client.
    """
    def __init__(self, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        """
        Constructor.
        :param workspace: Workspace name.
        :param host: IP address.
        :param port: Port number.
        """
        super().__init__(name="spa", workspace=workspace, host=host, port=port)


class TnTHsupP2IClient(TnTHsupClient):
    """
    This class implements pen-to-ink client.
    """
    def __init__(self, workspace=TnTClientObject.default_workspace, host="127.0.0.1", port=8000):
        """
        Constructor.
        :param workspace: Workspace name.
        :param host: IP address.
        :param port: Port number.
        """
        super().__init__(name="p2i", workspace=workspace, host=host, port=port)
