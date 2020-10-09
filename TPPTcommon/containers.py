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
import numpy
import math

class TestAction(object):
    """
    Base class for discrete test actions
    """

    def __init__(self):
        pass


class Point(TestAction):
    """
    Container class representing a single 3D point for tests
    """

    def __init__(self, x, y, z, fingers=1, finger_distance=0, angle=0.0, first_finger_offset=0.0):
        # These coordinates always refer to the active finger of one-finger or two-finger tool.
        self.x = x
        self.y = y
        self.z = z

        if fingers > 1 and finger_distance > 0:
            self.multifinger = True
        else:
            self.multifinger = False
        self.fingers = fingers
        self.finger_distance = finger_distance
        self.angle = angle
        self.first_finger_offset = first_finger_offset

    def __repr__(self):
        return "%s(%s) [x:%s; y:%s; z%s]" % (self.__class__.__name__, hex(id(self)), self.x, self.y, self.z)


class TouchAreaPoint(Point):
    """
    Container class representing a single 3D point with touch area information
    """

    def __init__(self, x, y, z, fingers=1, finger_distance=0, angle=0.0, first_finger_offset=0.0, touch_area=''):
        super().__init__(x, y, z, fingers, finger_distance, angle, first_finger_offset)
        self.touch_area = touch_area

    def __repr__(self):
        return super().__repr__() + ', region:{0}'.format(self.touch_area)


class Line(TestAction):
    """
    Container class representing a single 3D line between start and end points for tests
    """

    def __init__(self, start_x, start_y, start_z, end_x, end_y, end_z, fingers=1, finger_distance=0, angle=0.0,
                 first_finger_offset=0.0):
        # These coordinates always refer to the active finger of one-finger or two-finger tool.
        self.start_x = start_x
        self.start_y = start_y
        self.start_z = start_z
        self.end_x = end_x
        self.end_y = end_y
        self.end_z = end_z

        if fingers > 1 and finger_distance > 0:
            self.multifinger = True
        else:
            self.multifinger = False
        self.fingers = fingers
        self.finger_distance = finger_distance
        self.angle = angle
        self.first_finger_offset = first_finger_offset

    def __repr__(self):
        return "%s(%s) [start_x:%s; start_y:%s; start_z%s / end_x:%s; end_y:%s; end_z%s]" % (
        self.__class__.__name__, hex(id(self)), self.start_x, self.start_y, self.start_z, self.end_x, self.end_y,
        self.end_z)

    def length(self):
        return math.sqrt((self.start_x - self.end_x)**2 + (self.start_y - self.end_y)**2)


class Pinch(TestAction):
    """
    Container class representing a single pinch centered at a point for tests
    """

    def __init__(self, center_x, center_y, start_separation, end_separation, azimuth):
        self.center_x = center_x
        self.center_y = center_y
        self.start_separation = start_separation
        self.end_separation = end_separation
        self.azimuth = azimuth

    def __repr__(self):
        return "%s(%s) [center_x:%s; center_y:%s; start_separation:%s; end_separation:%s; azimuth:%s]" % (
            self.__class__.__name__, hex(id(self)), self.center_x, self.center_y, self.start_separation,
            self.end_separation, self.azimuth)


class Compass(TestAction):
    """
    Container class for a single compass motion with one finger motionless and the other moving in an arc around it
    """

    def __init__(self, center_x, center_y, separation, start_azimuth, end_azimuth):
        self.center_x = center_x
        self.center_y = center_y
        self.separation = separation
        # An azimuth of zero puts the rotating finger to the right of the stationary finger when looking from the
        # bottom of the test screen. Azimuth increases counter-clockwise in degrees.
        self.start_azimuth = start_azimuth
        self.end_azimuth = end_azimuth

    def __repr__(self):
        return "%s(%s) [center_x:%s; center_y:%s; separation:%s; start_azimuth:%s; end_azimuth:%s]" % (
            self.__class__.__name__, hex(id(self)), self.center_x, self.center_y, self.separation,
            self.start_azimuth, self.end_azimuth)

