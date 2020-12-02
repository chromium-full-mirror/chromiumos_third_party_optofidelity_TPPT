"""
Copyright (c) 2020, OptoFidelity OY
Copyright (c) 2020, The Chromium OS Authors

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
import logging

from sqlalchemy import Column, Integer, Boolean, Float, ForeignKey, VARCHAR
from sqlalchemy.orm import relationship

from MeasurementDB import CompassTest, CompassResults
from TPPTcommon.ConfigurationDatabase import ConfigurationDatabase
import TPPTcommon.containers as containers
from TPPTcommon.exceptions import GridCreationError, TipSelectionError
from TPPTcommon.grid import GridVisContainer
from TPPTcommon.TestStep import TestStep

logger = logging.getLogger(__name__)


class Compass(TestStep):
    """
    In this test case we perform compass gestures, where one finger moves in an arc around another, at various
    locations on the DUT.
    """

    def __init__(self, context):
        super().__init__('Compass')

        self.context = context

        self.database_configuration = CompassTestParameters

        sizes = [str(key) for (key, value) in sorted(context.tips_node.single_tips_by_size.items()) if len(value) >= 2]

        self.controls.finger_size = sizes[0] if len(sizes) > 0 else ""
        self.controls.info['finger_size'] = {'label': 'Finger size (mm)', 'items': sizes}

        self.controls.num_fingers = 2
        self.controls.info['num_fingers'] = {'label': 'Number of Fingers', 'min': 2, 'max': 2}

        self.controls.edge_width = 5.0
        self.controls.info['edge_width'] = {'label': 'Distance from edge (mm)'}

        self.speed = 30.0

    def execute(self):
        dut = self.context.get_active_dut()

        self.context.html("Running Compass test for dut:%s" % dut)

        test_item = self.context.create_db_test_item("Compass Test")

        measurement_compasses = self._create_grid(dut)

        for index, compass in enumerate(measurement_compasses):
            self.context.indicators.set_test_detail('Compass', str(index + 1) + ' / ' + str(len(measurement_compasses)))

            self.context.set_robot_default_speed()
            dut.jump(compass.center_x, compass.center_y, dut.base_distance, dut.base_distance)

            self.context.set_robot_speed(self.speed)

            continuous_measurement = self.context.create_continuous_measurement(compass)
            continuous_measurement.start()

            dut.compass(compass.center_x, compass.center_y, compass.start_azimuth, compass.end_azimuth,
                        compass.separation, clearance=-2)

            continuous_measurement.end()

            touch_list = continuous_measurement.parse_data()

            gesture_id = self._create_gesture(compass, test_item)
            self._save_measurement_data(gesture_id, touch_list)

            self.context.breakpoint()

        self.context.close_db_test_item(test_item)

    def _create_grid(self, dut):
        """
        Create grid of arcs that define the geometry of the test case.
        :param dut: DUT where the grid is evaluated on.
        """
        separation = self.context.get_min_separation(float(self.controls.finger_size))

        center_x = dut.width / 2
        center_y = dut.height / 2

        left = self.controls.edge_width
        right = dut.width - self.controls.edge_width
        top = self.controls.edge_width
        bottom = dut.height - self.controls.edge_width

        grid = [
            # Counter-clockwise around the DUT starting at top-left

            # Some compass gestures are 90 degrees, and some are 179. The robot API doesn't allow you to specify
            # rotation direction, and instead always takes the shortest path.  Using 179 degree arcs allows us to
            # specify the direction
            containers.Compass(left, top, separation, -90, 0),
            containers.Compass(left, center_y, separation, -90, 89),
            containers.Compass(left, bottom, separation, 0, 90),
            containers.Compass(center_x, bottom, separation, 0, 179),
            containers.Compass(right, bottom, separation, 90, 180),
            containers.Compass(right, center_y, separation, 90, 269),
            containers.Compass(right, top, separation, 180, 270),
            containers.Compass(center_x, top, separation, 180, 359),

            containers.Compass(center_x, center_y, separation, 0, 179),
            containers.Compass(center_x, center_y, separation, 180, 359)
        ]
        return grid

    def visualize_grid(self, dut):
        test_pattern = self._create_grid(dut)
        return GridVisContainer(self.__class__.__name__, (dut.width, dut.height), test_pattern, dut.name)

    def tip_is_valid(self):
        try:
            self.context.tips_node.select_tips_by_size(float(self.controls.finger_size), 2, check_only=True)
            return True
        except TipSelectionError as e:
            logger.error(str(e))
            return False

    def pattern_is_valid(self):
        dut = self.context.get_active_dut()
        try:
            _ = self._create_grid(dut)
            return True
        except GridCreationError as e:
            logger.error(str(e))
            return False

    def _create_gesture(self, compass, test_item):
        """
        Create gesture and add to database.
        :return: id of created gesture.
        """
        test = CompassTest()

        test.center_x = compass.center_x
        test.center_y = compass.center_y
        test.separation = compass.separation
        test.start_azimuth = compass.start_azimuth
        test.end_azimuth = compass.end_azimuth
        test.test_id = test_item.id
        test.finger_size = float(self.controls.finger_size)

        self.context.db.add(test)

        return test.id

    def _save_measurement_data(self, gesture_id, touch_list):
        """
        Save compass measurement to database.
        """
        db_list = []

        for test_result in touch_list:
            results = CompassResults()

            results.panel_x = float(test_result.panel_x)
            results.panel_y = float(test_result.panel_y)
            results.pressure = float(test_result.pressure)
            results.finger_id = int(test_result.finger_id)
            results.time = test_result.time
            results.event = test_result.event
            results.gesture_id = gesture_id

            db_list.append(results)

            self.context.add_dut_point(float(test_result.panel_x), float(test_result.panel_y))

        self.context.db.addAll(db_list)


class CompassTestParameters(ConfigurationDatabase.TestConfigBase):
    __tablename__ = 'compass_parameters'
    _id = Column('id', Integer, primary_key=True, autoincrement=True)
    _test_configuration = Column('test_configuration', Integer,
                                 ForeignKey('test_configuration.id', ondelete='CASCADE'))
    _test_configuration_orm = relationship('TestConfiguration', back_populates='_compass_configurations')

    enabled = Column(Boolean)
    finger_size = Column(VARCHAR(40))
    num_fingers = Column(Integer)
    edge_width = Column(Float)
