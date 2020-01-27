"""
This module implements command-line interface for running TPPT scripts directly from Python interpreter
without TnT UI.

To run TPPT as standalone, use test parameters stored in dry_run_parameters.json.
This file has content identical to history.json. Assuming that the json file has entry
"test_parameters", start dry run by executing:

> python standalone.py "test_parameters"

Currently Python 3.5 32-bit / 64-bit is supported.


Copyright (c) 2019, OptoFidelity OY

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
All advertising materials mentioning features or use of this software must display the following acknowledgement: This product includes software developed by the OptoFidelity OY.
Neither the name of the OptoFidelity OY nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
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
import logging
import time
import sys
import threading
import ruamel.yaml as yaml

from LoopSequence import  Context, STATE_WAITING
from drserver.server import DryRunThreadingServer
from drserver.tree import create_dry_run_tree

logger = logging.getLogger(__name__)

class UiProxyStandalone:
    """
    Proxy class for UI object that is used in standalone scheme.
    In this scheme script is executed directly by standalone Python interpreter without UI.

    Most interface functions are for UI interaction and are just dummy implementations in this class.
    """

    def __init__(self):
        self.context = None

    def create_dut_svg(self, x, y):
        pass

    def add_dut_point(self, x, y):
        pass
        #print("Touched {}, {}".format(x, y ))

    def clear_dut_points(self):
        pass

    def dialog_to_continue(self, message):
        print(message)
        input("Press enter to continue...")
        self.context.toggle_pause()

    def script_failed(self, message):
        print("Script failed: " + message)

    def script_finished(self):
        pass

    def change_to_figure_page(self):
        pass

    def hide_loading_element(self):
        pass

    def append_images_to_figure_page(self, images):
        pass

    def set_indicators(self, text):
        pass

    def log(self, message):
        logger.info(message)

    def set_script_nodes(self, node_dict):
        pass

    def set_script_parameters(self, parameters):
        pass

    def set_script_callables(self, callables):
        pass

    def set_configuration_group_headers(self, names, selected):
        pass

    def sys_log(self, message):
        logging.info(message)

    def set_history_headers(self, headers):
        pass

    def script_ready(self, success):
        pass


def start_dry_run_server(port=8000):
    """
    Start dry run server that provides REST API that is compatible with the TnT Client
    used by TPPT.
    :param port: Server port.
    """
    print("Starting dry run server.")

    with open("drconfig.yaml") as file:
        config = yaml.safe_load(file)

    create_dry_run_tree(config, poll_input=True, dut_comm=True)
    server = DryRunThreadingServer(("", port))

    def run_server():
        # This function blocks so it is ran in separate thread.
        server.serve_forever(1000)

    server_thread = threading.Thread(target=run_server)
    server_thread.start()

    return server, server_thread


def query_input(prompt, options=None, default=None):
    while True:
        if default is not None:
            prompt = prompt + " [{}]".format(default)

        result = input(prompt + ": ")

        if default is not None and len(result) == 0:
            return default

        if options is None:
            return result

        if result not in options:
            print("Invalid option '{}'!".format(result))
            continue

        return result


def run_standalone(name):
    """
    Run TPPT script as standalone.
    :param name: Name of history file entry to use to obtain script parameters.
    """
    server, server_thread = start_dry_run_server()

    ui = UiProxyStandalone()

    # Add log handler to pass script logs to UI process.
    root = logging.getLogger()

    # Change level to affect which messages are shown in UI console.
    root.setLevel(logging.INFO)

    print("Loading scripts.")

    # Create script context.
    context = Context(ui)
    ui.context = context

    input("Connect DUT application and press enter.")

    while True:
        sequence_type = query_input("Run single sequence (s) or group (g)", ["s", "g"], "s")

        if sequence_type == "g":
            context.active_group = input("Group name: ")

            print("Executing tests.")
            context.execute_tests(run_configuration_group=True)
        elif sequence_type == "s":
            file_path = query_input("Parameter file", None, "dry_run_parameters.json")

            # Load parameters from JSON file. The file has the same kind of content as history.yaml.
            print("Loading script parameters '{}'.".format(name))
            context.load(name, file_path=file_path)

            print("Executing tests.")
            context.execute_tests(run_configuration_group=False)

        # Wait for execution to complete.
        while context.state != STATE_WAITING:
            time.sleep(1)

        # Stop execution.
        context.stop()

        print("Finished")

        result = query_input("Run another sequence (yes / no)", ["yes", "no"], "yes")

        if result == "no":
            break

    server.server_close()
    server_thread.join()

    print("Server stopped")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise Exception("Missing required argument: history file entry name.")

    # Get history entry name from command line parameter list.
    name = sys.argv[1]

    run_standalone(name)
