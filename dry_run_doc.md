# TPPT dry run

## General

TPPT dry run is for running TPPT scripts without TnT Server and without physical robot. Instead each request made via TnT Client is directed to a *dry run server* which implements the same API as TnT Server. The dry run server will handle robot commands by giving human user instructions how to perform gestures. For example, tap gesture will draw a circle on DUT where user is supposed to tap with finger.

The same TPPT test cases and related analysis can be used in dry run environment without modifications.

## Setup

The dry run environment is delivered in source form and is hence not directly executable. Python 3.5 32-bit needs to be installed on the system and the system needs to have internet access to access the general pypi server.

### Windows

To set things up, open console (cmd.exe) in TPPT root directory. Then type

    py -3.5-32 -m venv venv

This will create a Python virtual environment in local directory `venv`.

Then type following

    venv\Scripts\Activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt

Now the virtual environment is setup for running the dry run tests.

### Linux

Install Python 3.6.8. This seems to be installed by default in Ubuntu 18.04 LTS. Install `venv` and `pip`:

sudo apt install python3-venv
sudo apt install python3-pip

To set things up, open terminal in TPPT root directory. Then type

    python3 -m venv venv

This will create a Python virtual environment in local directory `venv`.

Then type following

    source venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt

Now the virtual environment is setup for running the dry run tests.

## Running dry run tests

To launch dry run, activate the virtual environment as done during setup. Then type

    python standalone.py "test_parameters"

Here "test_parameters" is a name corresponding to an entry in `dry_run_parameters.json`. This json file has the same format as `history.json` which is produced by TnT UI to store test sequence paramters when sequence is started from the UI.

Follow the instructions printed in the terminal. The script prompts some input. Type the input and press enter to continue. Some prompts have a default value which is shown in parenthesis `[default_value]`. In that case press enter with no input to choose the default value.

## Configuring dry run environment

Dry run environment is configured in file `drconfig.yaml`. This file contains e.g. DUT and tip definitions that are required to run the dry run server.

For each DUT, one needs to specify its name, width in mm and height in mm. In the config file a valid DUT configuration would be e.g.

    duts:
        Dut1:
            width: 100
            height: 200

For each tip, one needs to specify its name and model. Valid models are `Standard` and `Multifinger`. In case the tip is multifinger tip, then following proerties must also be specified: `num_tips`, `tip_distance`, `first_finger_offset`, `separation`.

Valid tip configuration for standard and multifinger tips:

    tips:
      tip1:
        model: Standard
      multi5:
        model: Multifinger
        num_tips: 5
        tip_distance: 12
        first_finger_offset: 24
        separation: 48

## Configuring script parameters

Configuring the test script parameters is done via json file in contrast to the normal use case where TnT UI is used.

The json format used is the same as TnT UI uses to save script parameter history to `history.json` file. To use a specific set of parameters, user needs to specify an entry in the json file. In the history file, entry names are dates.

By default the dry run environment does not use the file `history.json` but instead a stripped down version `dry_run_parameters.json`. This file contains a single entry named `test_parameters`. It expects a DUT named `Dut1` and a tip named `tip1` to exist in the dry run environment. Open this file in a text editor to change the various test case parameters.

## Human operation during test cases

When a test case runs, it prints text to terminal to indicate the DUT coordinates (in mm) where user is supposed to touch with finger. Terminal then prompts to press enter when the gesture is completed. In addition, an image is sent to the DUT to illustrate how to perform the gesture.

Note that the test cases define certain time-outs for collecting touch data. This means that user has limited time available to perform the gesture once prompted.

### Tap test

When test script commands a tap gesture at DUT coordinate (15, 20), following is printed to terminal:

    Tap at 15, 20

Simultaneously, a blue circle is displayed on the DUT. User then has limited time (by default 3 seconds) to tap on the DUT screen with finger. After the tap is done, user will press enter on the terminal to continue.

### Linearity test

When test script commands a swipe gesture on DUT from point (15, 20) to (42, 20), following is printed to terminal:

    Swipe from 15, 20 to 42, 20

Simultaneously, a blue arrow is displayed on the DUT. User then has limited time (by default 3 seconds) to swipe on the DUT screen with finger. After the swipe is done, user will press enter on the terminal to continue.

### Stationary Jitter Static Noise test

In this test, the test script commands the robot to move on to the DUT screen and hold its position for a specific duration. When jitter test is performed at DUT coordinate (15, 20), following is printed to terminal:

    Touch and hold at 15, 20

Simultaneously, a blue circle is displayed on the DUT. User then has limited time (by default 3 seconds) to touch on the DUT screen with finger. After the gesture is done, user will press enter on the terminal to continue.

Performing this test case as human operator differs from other test cases. To get correct touch data, operator should touch the DUT location when instructed and keep on touching it while pressing enter to continue to the next step.

### Tapping Repetability test

This test is performed similar to Tap test but user is instructed to tap multiple times on the same location.
