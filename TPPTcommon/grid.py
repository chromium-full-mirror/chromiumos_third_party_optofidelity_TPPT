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
import collections
import matplotlib.pyplot as plt
import matplotlib.patches as pltpatches
import numpy
import math
import time
import os
import csv
import copy
import mimetypes
import cv2
import base64
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

try: import TPPTcommon.containers as Containers
except: import containers as Containers

def line_coord_of_closest_rectangle_intersection(min_x, max_x, start_x, dir_x):
    """
    Get closest parametric line coordinate of intersection point of the line and
    rectangle along one dimension.
    :param min_x: Rectangle minimum along selected dimension.
    :param max_x: Rectangle maximum along selected dimension.
    :param start_x: Line start point coordinate in selected dimension.
    :param dir_x: Line direction vector coordinate in selected dimension.
    :return: Line parameter at closest intersection.
    """

    # Direction vector determines which of the two possible rectangle edges is hit first.
    if dir_x > 0:
        return (min_x - start_x) / dir_x
    elif dir_x < 0:
        return (max_x - start_x) / dir_x

    # Direction is perpendicular to selected dimension. Return -1 so these planes are not hit.
    return -1


def clip_line_start_to_rectangle(line, width, height, border_width):
    """
    Clip line start to axis aligned rectangle center area (determined by border_width).
    If line is completely outside of the rectangle, the line is collapsed into a point.
    :param line: A line with start and end points.
    :param width: Width of the rectangle.
    :param height: Height of the rectangle.
    :param border_width: Border width of the rectangle.
    """

    # Line direction vector components.
    dx = line.end_x - line.start_x
    dy = line.end_y - line.start_y

    # Clip region min and max coordinates.
    min_x = border_width
    max_x = width - border_width
    min_y = border_width
    max_y = height - border_width

    # Determine line parameters for two potential closest hit points.
    tx = line_coord_of_closest_rectangle_intersection(min_x, max_x, line.start_x, dx)
    ty = line_coord_of_closest_rectangle_intersection(min_y, max_y, line.start_y, dy)

    # Line start is inside the rectangle
    if tx < 0 and ty < 0:
        return

    # Determine which of the two coordinates corresponds to closest hit point.
    if tx > ty:
        t = tx
        px = line.start_x + dx * t
        py = line.start_y + dy * t

        # Check if the hit point is within the region boundary.
        if min_y <= py <= max_y:
            line.start_x = px
            line.start_y = py
        else:
            line.start_x = line.end_x
            line.start_y = line.end_y
    else:
        t = ty
        px = line.start_x + dx * t
        py = line.start_y + dy * t

        # Check if the hit point is within the region boundary.
        if min_x <= px <= max_x:
            line.start_x = px
            line.start_y = py
        else:
            line.start_x = line.end_x
            line.start_y = line.end_y


def clip_line_to_rectangle(line, width, height, border_width):
    """
    Clip line to axis aligned rectangle center area (determined by border_width).
    :param line: A line with start and end points.
    :param width: Width of the rectangle.
    :param height: Height of the rectangle.
    :param border_width: Border width of the rectangle.
    :return:
    """

    # Clip line start point to region.
    clip_line_start_to_rectangle(line, width, height, border_width)

    # Swap line start and end points and again clip line start point to region. Then swap start and end points back.
    line.start_x, line.start_y, line.end_x, line.end_y = line.end_x, line.end_y, line.start_x, line.start_y
    clip_line_start_to_rectangle(line, width, height, border_width)
    line.start_x, line.start_y, line.end_x, line.end_y = line.end_x, line.end_y, line.start_x, line.start_y


def clip_lines_svg(dut, lines_all, border_width, region):
    """
    Clip lines to be inside defined of dut. If filtering the lines breaks them in
    multiple parts, all parts are saved as individual lines.
    :param dut: tnt_dut object
    :param lines_all: containers.lines drawn assuming dut is rectangle and with border width 0
    :param border_width: width of the border area
    :param region: the region used for clipping (test_region or analysis_region)
    :return: clipped containers.lines
    """
    lines_filtered = []
    line_end_points = []
    # the filtering function needs the endpoints of the lines
    for line in lines_all:
        line_end_points.append((line.start_x, line.start_y, line.end_x, line.end_y))
    line_end_points_filt = dut.filter_lines(line_end_points, region, border_width)
    for i, end_points in enumerate(line_end_points_filt):
        # if the line is discarded due to clipping, it is an empty group
        if len(end_points) > 0:
            # The line might be clipped in multiple parts (because of notch)
            for points in end_points:
                # copy the line from which the endpoints are and modify the copy with new endpoints and save
                filt_line = copy.copy(lines_all[i])
                filt_line.start_x, filt_line.start_y = points[0], points[1]
                filt_line.end_x, filt_line.end_y = points[2], points[3]
                lines_filtered.append(filt_line)
    return lines_filtered


def is_point_in_center_rectangle(point, width, height, border_width):
    """
    Check if given point is center point within region [0, width] x [0, height]
    that has given border.
    """
    if point.x < border_width or point.x > width - border_width:
        return False

    if point.y < border_width or point.y > height - border_width:
        return False

    return True


def is_point_in_center_svg(point, dut, border_width):
    """
    Check if given point is in the center area specified
    by svg graphics.
    :param point: containers.point object
    :param dut: tnt_dut object used via client
    :param border_width: the width of the border region
    :return: true if point is in center area, otherwise false
    """
    x, y = point.x, point.y
    # If point is in analysis_region with given marginal filter_points
    # will return a list containing the point.
    res= dut.filter_points([[x,y]], 'analysis_region', margin=border_width)
    if len(res) > 0:
        return True
    else:
        return False


def is_point_in_area(point, area, dut, border_width):
    """
    Check whether given point is within specified area ("edge_area", "center_area", or "corner_area").
    Currently corner_area and edge_area checking is the same and it is assumed the points are already
    in the corner region if corner is the chosen area.
    NOTE! Filtering points with svg one by one is slow and should be avoided.
    :param point: containers.point object
    :param area: the specified area
    :param dut: tnt_dut object
    :param border_width: width of the edge area
    :return: true if point is in the specified area, otherwise false
    """
    is_point_in_dut = False
    is_point_in_center = False
    if len(dut.svg_data()) > 0:
        is_point_in_dut = is_point_in_center_svg(point, dut, border_width=0)
        is_point_in_center = is_point_in_center_svg(point, dut, border_width)
    else:
        is_point_in_dut = True
        is_point_in_center = is_point_in_center_rectangle(point, dut.width, dut.height, border_width)

    if area == 'center_area':
        return is_point_in_center
    elif area == 'edge_area':
        return is_point_in_dut and not is_point_in_center
    elif area == 'corner_area':
        # Returns the same as 'edge_area' and it is assumed corner situation is handled elsewhere.
        # However, this is separated from 'edge_area' to add clarity to code in other parts
        return is_point_in_dut and not is_point_in_center
    else:
        raise Exception("{} is not allowed measurement area".format(area))


def azimuth_direction(azimuth_angle):
    '''
    Calculates unit vector for given azimuth angle.
    ----------------------------------------
    Why is this needed:

    In our robots, we use left hand convention for x-y-z-axis and right hand convention for azimuth angles.
    With other words, the z-axis points up from DUT, x-axis from top left corner to top right corner, and
    y-axis from top left corner to bottom left corner. However, the angle grows anti-clockwise.
    ----------------------------------------
    :param azimuth_angle: the angle for which we want the unit vector (radians)
    :return: unit vector as a list [x,y] for given azimuth angle
    '''

    x_comp = numpy.cos(-azimuth_angle)
    y_comp = numpy.sin(-azimuth_angle)

    return [x_comp, y_comp]

def calculate_multifinger_line(line, tip_ind):
    '''
    Calculates the expected trajectory for a certain finger of a multifinger tool
    based on the tool properties and the line drawn by the first finger
    :param line: the line of the first finger
    :param tip_ind: which finger is the current one, firs finger has 0 as index
    :return: Line object for the chosen finger id
    '''
    angle = line.angle
    unit_vec = azimuth_direction(numpy.radians(angle))
    offset = tip_ind * line.finger_distance

    offset_x = unit_vec[0] * offset
    offset_y = unit_vec[1] * offset

    start_x = line.start_x + offset_x
    start_y = line.start_y + offset_y
    start_z = 0
    end_x = line.end_x + offset_x
    end_y = line.end_y + offset_y
    end_z = 0

    # Even though the line we are returning is theoretically not a multifinger line
    # anymore, we should keep these values for analysis to indicate that this is a single line
    # separated from multifinger test
    num_tips = line.fingers
    tip_dist = line.finger_distance
    angle = line.angle

    return Containers.Line(start_x, start_y, start_z, end_x, end_y, end_z, num_tips, tip_dist, angle)

def calculate_multifinger_point(point, tip_ind):
    '''
    Calculates the expected trajectory for a certain finger of a multifinger tool
    based on the tool properties and the line drawn by the first finger
    :param point: the Point object calculated for the first finger
    :param tip_ind: which finger is the current one, first finger has 0 as index
    :return: Line object for the chosen finger id
    '''
    angle = point.angle
    unit_vec = azimuth_direction(numpy.radians(angle))
    offset = tip_ind * point.finger_distance

    offset_x = unit_vec[0] * offset
    offset_y = unit_vec[1] * offset

    x = point.x + offset_x
    y = point.y + offset_y
    z = 0

    # Even though the point we are returning is theoretically not a multifinger point
    # anymore, we should keep these values for analysis to tell indicate this is a single point
    # separated from multifinger test
    num_tips = point.fingers
    tip_dist = point.finger_distance
    angle = point.angle

    return Containers.Point(x, y, z, num_tips, tip_dist, angle)


def point_distance_to_line(line_start_coords, line_end_coords, point_coords):
    '''
    Calculates the orthogonal distance between given line and point. The end points
    of the line are not considered but line infinitely extended.
    :param line_start_coords: the starting point of the line [x, y]
    :param line_end_coords: the ending point of the line [x, y]
    :param point_coords: the point in form [x, y]
    :return: the distance value
    '''
    line_start_v = numpy.array(line_start_coords)
    line_end_v = numpy.array(line_end_coords)
    point_v = numpy.array(point_coords)
    cross_prod = numpy.cross(line_end_v - line_start_v, point_v - line_start_v)
    norm = numpy.linalg.norm(line_end_v - line_start_v)
    # Dividing by zero should be avoided
    if norm > 0:
        dist = abs(cross_prod / norm)
    else:
        dist = 0.0

    return dist

def point_distance_to_point(point_0, point_1):
    """
    Calculates to distance between two [x ,y] points.
    :param point_0: [x, y] point number 0
    :param point_1: [x, y] point number 1
    :return: distance between the points
    """
    return numpy.sqrt((point_0[0]-point_1[0])**2 + (point_0[1]-point_1[1])**2)


def point_dist_to_many_points_avg(comparison_point, touch_coords):
    '''
    Calculates average of the shortest distances between list of points and a Point object
    :param comparison_point: the robot point as Point object
    :param touch_coords: list of coordinates ([[x1, y1],[x2, y2],[x3, y3],...])
    :return: average of the distances between robot and recorded points
    '''
    distances = []
    # Calculate distance for every point
    comp_coord = [comparison_point.x, comparison_point.y]
    for coord in touch_coords:
        dist = point_distance_to_point(comp_coord, coord)
        distances.append(dist)
    distance_avg = numpy.average(numpy.array(distances))

    return distance_avg

def line_dist_to_many_points_avg(comparison_line, touch_coords):
    '''
    Calculates average of the shortest distances between list of points and a Line object
    :param comparison_line: the Line object
    :param touch_coords: list of coordinates ([[x1, y1],[x2, y2],[x3, y3],...])
    :return: average of the distances between line and points
    '''
    distances = []
    # Calculate distance of every point
    line_start = [comparison_line.start_x, comparison_line.start_y]
    line_end = [comparison_line.end_x, comparison_line.end_y]
    for coord in touch_coords:
        dist = point_distance_to_line(line_start, line_end, coord)
        distances.append(dist)
    distance_avg = numpy.average(numpy.array(distances))

    return distance_avg

def separate_multifinger_events(touchlist_all):
    """
    Separates touchevents from a recording based on the finger id
    :param touchlist_all: recorded touchlist
    :return: dict that has finger ids as keys and touchevents as values
    """
    separated_events = {}
    for event in touchlist_all:
        # event: [x, y, z, finger_id, ?, timestamp, event_type]
        finger_id = event[3]
        if finger_id not in separated_events:
            separated_events[finger_id] = []
        separated_events[finger_id].append(event)
    return separated_events


class GridVisContainer():
    """
    Container for grid visualization. Contains all elements needed to visualize a test grid.
    Args:
    name: string
    panel_size: (width, height)
    items: List of objects derived from containers.TestAction to be plotted
    title: string [sub-plot title; e.g. DUT name]
    """
    def __init__(self, name, panel_size, items, title=None, projection_3d=False):
        self.name = name
        self.panel_size = panel_size
        self.items = items
        self.title = title
        self.projection_3d = projection_3d

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, hex(id(self)))

class GridVisualizer():
    """
    Class that is used to generate measurement point figures
    Usage:
        gv = GridVisualizer()
        gv.AddGridList(gridlist) # gv.AddGrid(grid) See AddGrid() or AddGridList()
        images = gv.Render()
    """
    def __init__(self):
        self.figure = Figure()
        self.grids = {}

    def Render(self):
        """
        Main rendering function, generates test grid images
        :return: Dictionary { 'test case name' : [list of plotted images] }
        """
        images = {}

        fig = self.figure
        fig_canvas = FigureCanvas(fig)

        for gesture in self.grids:
            grids = self.grids[gesture]

            if not isinstance(grids, collections.Iterable):
                grids = [grids]

            for grid_n in range(len(grids)):
                ax_n = 111
                active_grid = grids[grid_n]
                if active_grid.projection_3d: ax = fig.add_subplot(ax_n, title=active_grid.title, projection='3d')
                else: ax = fig.add_subplot(ax_n, title=active_grid.title)
                points = [[], [], [], []]

                normals = []
                for i in active_grid.items:
                    if isinstance(i, Containers.Point):
                        multi = False
                        try: multi = i.multifinger
                        except: pass
                        if multi:
                            multi_finger_points = self._CreateMultifingerTapPoints(i, i.angle)
                            for multi_finger_point in multi_finger_points:
                                points[0].append(multi_finger_point[0])
                                points[1].append(multi_finger_point[1])
                                points[2].append(multi_finger_point[2])
                                points[3].append(multi_finger_point[3])
                        else:
                            points[0].append(i.x)
                            points[1].append(i.y)
                            points[2].append(i.z)
                            if isinstance(i, Containers.TouchAreaPoint) and i.touch_area == 'edge_area':
                                points[3].append('r')
                            else:
                                points[3].append('b')


                    elif isinstance(i, Containers.Line):
                        multi = False
                        try: multi = i.multifinger
                        except: pass
                        if not multi:
                            color = "blue"
                            try: color = i.color
                            except:pass
                            if not active_grid.projection_3d: ax.arrow(i.start_x, i.start_y, i.end_x - i.start_x, i.end_y - i.start_y, head_width=2, head_length=2, fc=color, ec=color)
                            else: ax.plot([i.start_x, i.end_x], [i.start_y, i.end_y], zs = [i.start_z, i.end_z], color=color)
                        else:
                            arrows = self._CreateMultifingerLineArrows(i)
                            for arrow in arrows:
                                ax.arrow(arrow[0],arrow[1],arrow[2],arrow[3], head_width=arrow[4], head_length=arrow[5], fc=arrow[6], ec=arrow[6])

                if active_grid.projection_3d:
                    ax.scatter(points[0], points[1], points[2], color=points[3])
                    for normal in normals:
                        ax.plot(normal[0], normal[1], normal[2], linewidth=2)

                    max_range = numpy.array([max(points[0]) - min(points[0]), max(points[1]) - min(points[1]), max(points[2]) - min(points[2])]).max() / 2.0
                    mid_x = (max(points[0]) + min(points[0])) * 0.5
                    mid_y = (max(points[1]) + min(points[1])) * 0.5
                    mid_z = (max(points[2]) + min(points[2])) * 0.5
                    ax.set_xlim(mid_x - max_range, mid_x + max_range)
                    ax.set_ylim(mid_y + max_range, mid_y - max_range)
                    ax.set_zlim(mid_z - max_range, mid_z + max_range)
                else:
                    ax.scatter(points[0], points[1], color=points[3])

                if not active_grid.projection_3d:
                    ax.add_patch(pltpatches.Rectangle([0,0], active_grid.panel_size[0], active_grid.panel_size[1], edgecolor='black', fill=False))
                    ax.axis([-10, active_grid.panel_size[0] + 10, active_grid.panel_size[1] + 10, -10])
                    ax.set_xlabel("Measurement area width " + str(numpy.around(active_grid.panel_size[0], 2)) + " [mm]")
                    ax.set_ylabel("Measurement area height " + str(numpy.around(active_grid.panel_size[1],2)) + " [mm]")
                    ax.set_aspect('equal')
                else:
                    pass

                if gesture not in images:
                    images[gesture] = []
                images[gesture].append(self._fig_to_canvas(fig_canvas))

                fig.clear()

        return images

    def autowrap_text(self, textobj, renderer):
        """Wraps the given matplotlib text object so that it exceed the boundaries
        of the axis it is plotted in."""
        import textwrap
        # Get the starting position of the text in pixels...
        x0, y0 = textobj.get_transform().transform(textobj.get_position())
        # Get the extents of the current axis in pixels...
        clip = textobj.get_axes().get_window_extent()
        # Set the text to rotate about the left edge (doesn't make sense otherwise)
        textobj.set_rotation_mode('anchor')

        # Get the amount of space in the direction of rotation to the left and
        # right of x0, y0 (left and right are relative to the rotation, as well)
        rotation = textobj.get_rotation()
        right_space = self.min_dist_inside((x0, y0), rotation, clip)
        left_space = self.min_dist_inside((x0, y0), rotation - 180, clip)

        # Use either the left or right distance depending on the horiz alignment.
        alignment = textobj.get_horizontalalignment()
        if alignment is 'left':
            new_width = right_space
        elif alignment is 'right':
            new_width = left_space
        else:
            new_width = 2 * min(left_space, right_space)

        # Estimate the width of the new size in characters...
        aspect_ratio = 0.5  # This varies with the font!!
        fontsize = textobj.get_size()
        pixels_per_char = aspect_ratio * renderer.points_to_pixels(fontsize)

        # If wrap_width is < 1, just make it 1 character
        wrap_width = max(1, new_width // pixels_per_char)
        try:
            wrapped_text = textwrap.fill(textobj.get_text(), wrap_width)
        except TypeError:
            # This appears to be a single word
            wrapped_text = textobj.get_text()
        textobj.set_text(wrapped_text)

    def min_dist_inside(self, point, rotation, box):
        """Gets the space in a given direction from "point" to the boundaries of
        "box" (where box is an object with x0, y0, x1, & y1 attributes, point is a
        tuple of x,y, and rotation is the angle in degrees)"""
        from math import sin, cos, radians
        x0, y0 = point
        rotation = radians(rotation)
        distances = []
        threshold = 0.0001
        if cos(rotation) > threshold:
            # Intersects the right axis
            distances.append((box.x1 - x0) / cos(rotation))
        if cos(rotation) < -threshold:
            # Intersects the left axis
            distances.append((box.x0 - x0) / cos(rotation))
        if sin(rotation) > threshold:
            # Intersects the top axis
            distances.append((box.y1 - y0) / sin(rotation))
        if sin(rotation) < -threshold:
            # Intersects the bottom axis
            distances.append((box.y0 - y0) / sin(rotation))
        return min(distances)

    def _fig_to_canvas(self, fig_canvas):
        fig_canvas.draw()

        width, height = self.figure.get_size_inches() * self.figure.get_dpi()
        width = int(width)
        height = int(height)

        frame = numpy.fromstring(fig_canvas.tostring_rgb(), dtype='uint8').reshape(height, width, 3)
        bd = GridVisualizer.ndarray_to_img_src(frame, ".png")
        return bd

    def ndarray_to_img_src(image: numpy.ndarray, type=".jpg"):
        """Convert image into img.src source string"""
        mimetype, encoding = mimetypes.guess_type("base" + type)
        mimetype = mimetype if mimetype is not None else 'image/jpeg'
        r, data = cv2.imencode(type, image)
        bd = base64.b64encode(data)
        bd = "data:" + mimetype + ";base64," + bd.decode()
        return bd

    def _CreateMultifingerLineArrows(self, line):
        colour_LUT = ['#0000FF',
                      '#00FF00',
                      '#FF00FF',
                      '#00FFFF',
                      '#FFFF00',
                      '#FFA600',
                      '#8CFF00',
                      '#CC00FF',
                      '#FF7AB6',
                      '#000000',
                      '#7D7D7D']
        retval = []
        start_x = line.start_x
        start_y = line.start_y
        end_x = line.end_x
        end_y = line.end_y
        retval.append((start_x, start_y, end_x - start_x, end_y - start_y, 2, 2, colour_LUT[0]))

        angle = line.angle
        unit_vec = azimuth_direction(numpy.radians(angle))
        for i in range(line.fingers - 1):
            x_t = (i + 1) * line.finger_distance * unit_vec[0]
            y_t = (i + 1) * line.finger_distance * unit_vec[1]
            retval.append((start_x + x_t, start_y + y_t, end_x - start_x, end_y - start_y, 2, 2, colour_LUT[i + 1]))

        return retval

    def _CreateMultifingerTapPoints(self, point, angle=0.0):
        colour_LUT = ['#0000FF',
                      '#00FF00',
                      '#FF00FF',
                      '#00FFFF',
                      '#FFFF00',
                      '#FFA600',
                      '#8CFF00',
                      '#CC00FF',
                      '#FF7AB6',
                      '#000000',
                      '#7D7D7D']
        retval = []
        retval.append((point.x, point.y, 0.0, colour_LUT[0]))

        unit_vec = azimuth_direction(numpy.radians(angle))

        for i in range(point.fingers - 1):
            x_t = (i + 1) * point.finger_distance * unit_vec[0]
            y_t = (i + 1) * point.finger_distance * unit_vec[1]
            retval.append((point.x + x_t, point.y + y_t, 0.0, colour_LUT[i + 1]))

        return retval

    def AddGrid(self, name, grid):
        """
        Adds a single grid for visualization:
        args:
        name: name of the group(Test name usually) to add the grid to.
        grid: GridVisContainer-object
        """
        if name in self.grids:self.grids[name].append(grid)
        else:self.grids[name] = [grid]

    def AddGridList(self, griddict):
        """
        Adds a dictionary of grids for visualization:
        args:
        griddict: {"name":[GridVisContainer,],}
        """
        self.grids = {**self.grids, **griddict}

    def ClearGrids(self):
        """
        Clears all grids.
        """
        self.grids = {}


def create_point_nmm_grid_scaled(dut, step, direction="vertical"):
    """
    Creates a uniform grid on points inside rectangle specified by
    dut dimensions
    :param dut: tnt_dut
    :param step: distance between two points
    :param direction: direction in which the next points are added
    :return: list of Containers.Points objects
    """
    retval = []

    w_ = dut.width
    h_ = dut.height

    w_points = int(numpy.round(w_ / step))
    if w_points == 0: w_points = 1
    h_points = int(numpy.round(h_ / step))
    if h_points == 0: h_points = 1
    w_real_step = w_ / w_points
    h_real_step = h_ / h_points

    if direction == "vertical":
        for x_ in range(w_points + 1):
            for y_ in range(h_points + 1):
                point = Containers.Point(x_ * w_real_step, y_ * h_real_step, 0)
                retval.append(point)
    elif direction == "horizontal":
        for y_ in range(h_points + 1):
            for x_ in range(w_points + 1):
                point = Containers.Point(x_ * w_real_step, y_ * h_real_step, 0)
                retval.append(point)
    else:
        raise Exception("Invalid grid direction")

    return retval

def create_grid_accuracy_grid(dut, step_size, touch_area, border_width):
    """
    Chooses the correct function to create the grid accuracy points
    :param dut: tnt_dut object
    :param step_size: distance between points
    :param touch_area: 'center_area' or 'edge_area'
    :param border_width: width of the edge area
    :return: list of Containers.Points
    """
    if len(dut.svg_data()) > 0:
        return create_grid_accuracy_grid_svg(dut, step_size, touch_area, border_width)
    else:
        return create_grid_accuracy_grid_rectangle(dut, step_size, touch_area, border_width)

def create_grid_accuracy_grid_svg(dut, step_size, area, border_width):
    """
    Creates grid for grid accuracy test based on the dut svg image
    :param dut: tnt_dut object
    :param step_size: distance between points
    :param area: 'center_area' or 'edge_area'
    :param border_width:  widht of the edge area
    :return: list of Containers.Points
    """
    # Create point grid inside a rectangle that surrounds the dut
    rectangle_points = create_point_nmm_grid_scaled(dut, step_size, "horizontal")
    # Change the Containers.Points to coordinate pairs needed for filtering functions
    point_coords = []
    for point in rectangle_points:
        point_coords.append((point.x, point.y))
    # Get the center points. We don't want to tap on possible notch area -> using 'analysis_region'
    center_points = dut.filter_points(point_coords, 'analysis_region', border_width)
    if area == 'center_area':
        # With center_area just choose the already filtered points
        touch_points = center_points
    elif area == 'edge_area':
        edge_points = []
        # Find all the points that are inside the dut area
        all_points = dut.filter_points(point_coords, 'analysis_region', margin=0)
        # Filter away the points that are in center area leaving only edge points
        for point in all_points:
            if point not in center_points:
                edge_points.append(point)
        touch_points = edge_points
    else:
        raise Exception('Invalid touch area: {}'.format(area))
    # Create Containers.Point objects from the coordinate list
    final_points = []
    for point in touch_points:
        final_points.append(Containers.Point(point[0], point[1], 0))
    return final_points

def create_grid_accuracy_grid_rectangle(dut, step_size, area, border_width):
    """
    Creates grid accuracy points assuming that dut is a rectangle
    :param dut: tnt_dut
    :param step_size: distance between points
    :param area: 'center_area' or 'edge_area'
    :param border_width: width of the edge area
    :return: list of Containers.Points
    """
    # Create point grid for the whole dut surface
    all_points = create_point_nmm_grid_scaled(dut, step_size, "horizontal")
    final_points = []
    # Filter points based on the specified measurement area
    for point in all_points:
        if is_point_in_area(point, area, dut, border_width):
            final_points.append(point)

    return final_points

def create_stationary_jitter_static_noise_grid(dut, step_size, touch_area="center_area", border_width = 0, separation=0):
    """
    Creates measurement grid for stationary jitter static noise test.
    :param dut: tnt_dut
    :param step_size: distance_between points
    :param touch_area: 'center_area' or 'edge_area'
    :param border_width: width of the edge area
    :param separation: distance between the fingers in two-finger tool
    :return: list of Containers.Points
    """

    # The grid is the same as for grid accuracy but with the second finger settings added
    points = create_grid_accuracy_grid(dut, step_size, touch_area, border_width)
    set_stationary_jitter_static_noise_point_settings(dut, points, separation)
    return points

def set_stationary_jitter_static_noise_point_settings(dut, point_list, separation):
    """
    Modifies the settings for second finger for list of Containers.Point object
    :param dut: tnt_dut
    :param point_list: list of Containers.Points
    :param separation: distance between the fingers in two-finger tool
    :return: Nothing (modifies the point list)
    """
    dut_height = dut.height
    for point in point_list:
        # Determine azimuth angle based on tap location so that the second finger fits within the screen.
        if point.y < dut_height / 2:
            point.angle = -90
        else:
            point.angle = 90

        point.finger_distance = separation
        point.fingers = 2
        point.multifinger = True


def create_multi_swipe_horizontal(dut, num_of_fingers, finger_distance, border_width):
    """
    In horizontal multifinger swipe we want to do one swipe in the middle of the screen
    :param dut: the target dut
    :param num_of_fingers: number of fingers in the multifinger tool
    :param finger_distance: distance between fingers in the multifinger tool
    :param border_width: width of the border area
    :return: List of Container.Line object(s)
    """
    dut_width = dut.width
    dut_height = dut.height
    tool_width = (num_of_fingers-1)*finger_distance

    # Check that we can do the swipe
    if (dut_height - 2*border_width) > tool_width:
        # The middle point of the tool should be in the middle of the DUT screen
        start_x = 0 + border_width
        start_y = dut_height/2 - tool_width/2
        start_z = 0
        end_x = dut_width - border_width
        end_y = start_y
        end_z = 0
        angle = -90 #horizontal line
        line_list = [Containers.Line(start_x, start_y, start_z, end_x, end_y, end_z, num_of_fingers, finger_distance, angle)]
        # If dut cannot be assumed to be rectangle we need to do additional check
        if len(dut.svg_data()) > 0:
            clipped_lines = clip_lines_svg(dut, line_list, border_width, 'test_region')
            if len(clipped_lines) > 0:
                return [clipped_lines[0]]
            else:
                raise Exception("Multifinger width greater than DUT width (-borders), cannot do vertical swipe")
        else:  # dut can be assumed to be rectangle
            return line_list
    else:
        raise Exception("Multifinger width greater than DUT height (-borders), cannot do horizontal swipe")


def create_multi_swipe_vertical(dut, num_of_fingers, finger_distance, border_width):
    """
    In vertical multifinger swipe we want to do one swipe in the middle of the screen
    :param dut: the target dut
    :param num_of_fingers: number of fingers in the multifinger tool
    :param finger_distance: distance between fingers in the multifinger tool
    :param border_width: width of the border area
    :return: List of Container.Line object(s)
    """
    dut_width = dut.width
    dut_height = dut.height
    tool_width = (num_of_fingers - 1) * finger_distance

    # Check that we can do the swipe
    if (dut_width - 2*border_width) > tool_width:
        # The middle point of the tool should be in the middle of the DUT screen
        start_x = dut_width / 2 - tool_width / 2
        start_y = 0 + border_width
        start_z = 0
        end_x = start_x
        end_y = dut_height - border_width
        end_z = 0
        angle = 0  # vertical line
        line_list = [Containers.Line(start_x, start_y, start_z, end_x, end_y, end_z, num_of_fingers, finger_distance, angle)]
        # If dut cannot be assumed to be rectangle we need to do additional check
        if len(dut.svg_data()) > 0:
            clipped_lines = clip_lines_svg(dut, line_list, border_width, 'test_region')
            if len(clipped_lines) > 0:
                return [clipped_lines[0]]
            else:
                raise Exception("Multifinger width greater than DUT width (-borders), cannot do vertical swipe")
        else: # dut can be assumed to be rectangle
            return line_list
    else:
        raise Exception("Multifinger width greater than DUT width (-borders), cannot do vertical swipe")
    pass


def create_multi_swipe_diagonal(dut, num_of_fingers, finger_distance, border_width):
    """
    In diagonal multifinger swipe we want to do two swipes along both of the
    diagonals in the middle of the screen
    :param dut: the target dut
    :param num_of_fingers: number of fingers in the multifinger tool
    :param finger_distance: distance between fingers in the multifinger tool
    :param border_width: width of the border area
    :return: List of Container.Line object(s)
    """
    dut_width = dut.width
    dut_height = dut.height
    tool_width = (num_of_fingers - 1) * finger_distance
    lines = []
    # If swipe is shorter than this an error will be raised <- the tool is too wide for the DUT
    MIN_SWIPE_LENGTH = 2 #mm

    for start_point in ['top_left', 'top_right']:
        if start_point == 'top_left':
            start_corner = [0, 0]
            end_corner = [dut_width, dut_height]
            # The swipe is done diagonally. This is the angle between swipe and dut in width (x) direction
            # x-axis is the zero axis and anti-clockwise is positive direction
            swipe_angle = -numpy.degrees(numpy.arctan2(dut_height, dut_width))
            # We need to rotate the tool to make it perpendicular to the swipe angle
            azimuth_offset = -90
        else: # start_point == 'top_right'
            start_corner = [dut_width, 0]
            end_corner = [0, dut_height]
            # The swipe is done diagonally. This is the angle between swipe and dut in width (x) direction
            # x-axis is the zero axis and anti-clockwise is positive direction
            swipe_angle = -(180-numpy.degrees(numpy.arctan2(dut_height, dut_width)))
            # We need to rotate the tool to make it perpendicular to the swipe angle
            azimuth_offset = 90

        # The tool azimuth angle that needs to be perpendicular to the swipe angle
        # additionally the first finger needs to be "higher" than the last
        azimuth = swipe_angle + azimuth_offset
        # The unit components of the swipe normal vector
        unit_vec = azimuth_direction(numpy.radians(azimuth))

        # Next we calculate the line the first finger has when the tool mid point
        # travels accross the diagonal. This is done by moving the end and start points
        # by the amount and direction of half of the tool.
        start_x = start_corner[0] - (tool_width/2) * unit_vec[0]
        start_y = start_corner[1] - (tool_width/2) * unit_vec[1]
        start_z = 0
        end_x = end_corner[0] - (tool_width / 2) * unit_vec[0]
        end_y = end_corner[1] - (tool_width / 2) * unit_vec[1]
        end_z = 0

        # then the line needs to be clipped to take border width into account
        line_first = Containers.Line(start_x, start_y, start_z, end_x, end_y, end_z,
                                     num_of_fingers, finger_distance, azimuth)
        if len(dut.svg_data()) > 0:
            clipped_lines = clip_lines_svg(dut, [line_first], border_width, 'test_region')
            if len(clipped_lines) > 0:
                line_first = clipped_lines[0]
            else:
                raise Exception(
                    "Multifinger width greater than DUT diagonal width (-borders), cannot do diagonal swipe")
        else:
            clip_line_to_rectangle(line_first, dut_width, dut_height, border_width)

        # Then we do the same for the for the last finger. The only difference from the first finger is
        # that the "half-tool-vector" is in opposite direction:
        start_x = start_corner[0] + (tool_width / 2) * unit_vec[0]
        start_y = start_corner[1] + (tool_width / 2) * unit_vec[1]
        start_z = 0
        end_x = end_corner[0] + (tool_width / 2) * unit_vec[0]
        end_y = end_corner[1] + (tool_width / 2) * unit_vec[1]
        end_z = 0

        # then the line needs to be clipped to take border width into account
        line_last = Containers.Line(start_x, start_y, start_z, end_x, end_y, end_z,
                                    num_of_fingers, finger_distance, azimuth)
        if len(dut.svg_data()) > 0:
            clipped_lines = clip_lines_svg(dut, [line_last], border_width, 'test_region')
            if len(clipped_lines) > 0:
                line_last = clipped_lines[0]
            else:
                raise Exception(
                    "Multifinger width greater than DUT diagonal width (-borders), cannot do diagonal swipe")
        else:
            clip_line_to_rectangle(line_last, dut_width, dut_height, border_width)

        # Depending on the dut shape we need to either limit the start or end of the
        # first finger line by the last finger line
        if dut_width > dut_height:
            line_first.end_x = line_last.end_x - tool_width*unit_vec[0]
            line_first.end_y = line_last.end_y - tool_width*unit_vec[1]
        else: # dut_width <= dut_height
            line_first.start_x = line_last.start_x - tool_width*unit_vec[0]
            line_first.start_y = line_last.start_y - tool_width*unit_vec[1]

        # Checking if the resulting line is long enough
        line_length = line_first.length()
        if line_length <= MIN_SWIPE_LENGTH:
            raise Exception("Multifinger width greater than DUT diagonal width (-borders), cannot do diagonal swipe")

        lines.append(line_first)

    return lines


def create_multi_finger_tap_grid(dut, num_fingers, finger_dist):
    """
    Creates list of points for the first finger of a multifinger tool. Tries to do all tap directions,
    one tap so that the tool midpoint is in the middle of the screen: both diagonals, horizontal, and vertical.
    Raises an exception if none of the tap directions is possible due to the tool <-> DUT size difference
    :param dut: the target dut (DUT object)
    :param num_fingers: number of finger attached to the tool
    :param finger_dist: the distance between two adjacent fingers
    :return: list of Point objects
    """

    taps = []

    dut_width = dut.width
    dut_height = dut.height
    dut_diagonal = numpy.sqrt(dut_width**2+dut_height**2)

    tool_size = (num_fingers-1)*finger_dist

    # Checking if diagonal tap can be don assuming the dut is rectangle, the non-rectangle
    # case will be checked after we have value for the cornermost point
    if dut_diagonal < tool_size: # diagonal always has the greatest value
        raise Exception("Multifinger width greater than DUT diagonal, cannot do multifinger tap test")
    else:
        # We'll do diagonal tap in every case and it'll be done on both diagonals
        for start_corner in ('top_left', 'top_right'):
            # some things change depeding on which diagonal we are using
            if start_corner == 'top_left':
                start_coord = [0, 0]
                # 0 tool angle is the DUT x-axis (~width direction)
                tool_angle = -(numpy.degrees(numpy.arctan2(dut_height, dut_width)))
            else: # start_corner == top_right
                start_coord = [dut_width, 0]
                # 0 tool angle is the DUT x-axis (~width direction)
                tool_angle = -(180-numpy.degrees(numpy.arctan2(dut_height, dut_width)))

            # Calculating coordinates for the first finger of the tool for diagonal tap
            unit_vec = azimuth_direction(numpy.radians(tool_angle))
            dist_from_corner = dut_diagonal/2 - tool_size/2
            x = start_coord[0] + dist_from_corner*unit_vec[0]
            y = start_coord[1] + dist_from_corner*unit_vec[1]
            z = 0
            point = Containers.Point(x, y, z, num_fingers, finger_dist, tool_angle)
            # At this point we check if diagonal tap is ok for non-rectangle dut
            if len(dut.svg_data()) > 0:
                if not is_point_in_area(point, 'center_area', dut, border_width=0):
                    raise Exception("Multifinger width greater than DUT diagonal, cannot do multifinger tap test")
            taps.append(point)
        # Then we check the vertical, this is the same for non-rectangle dut (corners rounded)
        if tool_size <= dut_height:
            tool_angle = -90 #degrees
            x = dut_width / 2
            y = dut_height/2 - tool_size/2
            z = 0
            point = Containers.Point(x, y, z, num_fingers, finger_dist, tool_angle)
            taps.append(point)
        # Then the horizontal tap, this is the same for non-rectangle dut (corners rounded)
        if tool_size <= dut_width:
            tool_angle = 0
            x = dut_width/2 - tool_size/2
            y = dut_height/2
            z = 0
            point = Containers.Point(x, y, z, num_fingers, finger_dist, tool_angle)
            taps.append(point)
    return taps


def create_nmm_diagonal_lines(dut, spacing, border_width):
    """
    Chooses which function should be used for creation of evenly
    spaced diagonal lines.
    :param dut: tnt_dut object
    :param spacing: distance between two adjacent lines
    :param border_width: width of the edge area
    :return: list of containers.lines
    """
    if len(dut.svg_data()) > 0:
        return create_nmm_diagonal_lines_svg(dut, spacing, border_width)
    else:
        return create_nmm_diagonal_lines_rectangle(dut, spacing, border_width)


def create_nmm_diagonal_lines_svg(dut, spacing, border_width):
    """
   Create diagonal lines assuming the dut is rectangle and then clip them based
   on dut svg borders
   :param dut: tnt_dut object
   :param spacing: distance between two adjacent lines
   :param border_width: width of the edge area
   :return: list of clipped containers.lines
   """
    lines_all = create_nmm_diagonal_lines_rectangle(dut, spacing, border_width=0)
    return clip_lines_svg(dut, lines_all, border_width, 'analysis_region')


def create_nmm_diagonal_lines_rectangle(dut, spacing, border_width):
    retval = []

    w_ = dut.width
    h_ = dut.height

    delta_x = spacing / (math.sin(math.atan(h_ / w_)))
    delta_y = delta_x * (h_ / w_)

    # Horizontal lines
    start_point = [0.0, 0.0]
    end_point = [w_, h_]
    i = 1
    while True:
        if start_point[0] + delta_x * i > w_ or start_point[0] + delta_x * i < 0.0 or end_point[
            1] - delta_y * i < 0.0:
            break

        line = Containers.Line(delta_x * i, 0.0, 0.0, end_point[0], end_point[1] - delta_y * i, 0.0)
        clip_line_to_rectangle(line, w_, h_, border_width)

        if line.length() > 0:
            retval.append(line)
        i += 1
    i = 0
    while True:
        if start_point[0] + delta_x * i > w_ or start_point[0] + delta_x * i < 0.0 or end_point[
            1] - delta_y * i < 0.0:
            break
        line = Containers.Line(0.0, delta_y * i, 0.0, end_point[0] - delta_x * i, end_point[1], 0.0)

        clip_line_to_rectangle(line, w_, h_, border_width)

        if line.length() > 0:
            retval.append(line)
        i += 1
    i = 1
    while True:
        if start_point[0] + delta_x * i > w_ or start_point[0] + delta_x * i < 0.0 or end_point[
            1] - delta_y * i < 0.0:
            break

        line = Containers.Line(w_ - delta_x * i, 0.0, 0.0, 0.0, h_ - delta_y * i, 0.0)

        clip_line_to_rectangle(line, w_, h_, border_width)

        if line.length() > 0:
            retval.append(line)
        i += 1
    i = 0
    while True:
        if start_point[0] + delta_x * i > w_ or start_point[0] + delta_x * i < 0.0 or end_point[
            1] - delta_y * i < 0.0:
            break

        line = Containers.Line(w_, delta_y * i, 0.0, delta_x * i, h_, 0.0)

        clip_line_to_rectangle(line, w_, h_, border_width)

        if line.length() > 0:
            retval.append(line)
        i += 1
    return retval

def create_nmm_vertical_lines(dut, spacing, border_width):
    """
    Chooses which function should be used for creating the evenly
    spaced vertical lines
    :param dut: tnt_dut object
    :param spacing: distance between two adjacent lines
    :param border_width: width of the edge area
    :return: list of containers.lines
    """
    if len(dut.svg_data()) > 0:
        return create_nmm_vertical_lines_svg(dut, spacing, border_width)
    else:
        return create_nmm_vertical_lines_rectangle(dut, spacing, border_width)

def create_nmm_vertical_lines_svg(dut, spacing, border_width):
    """
   Create vertical lines assuming the dut is rectangle and then clip them based
   on dut svg borders
   :param dut: tnt_dut object
   :param spacing: distance between two adjacent lines
   :param border_width: width of the edge area
   :return: list of clipped containers.lines
   """
    lines_all = create_nmm_vertical_lines_rectangle(dut, spacing, border_width=0)
    return clip_lines_svg(dut, lines_all, border_width, 'analysis_region')


def create_nmm_vertical_lines_rectangle (dut, spacing, border_width=0):
    retval = []

    w_ = dut.width
    h_ = dut.height
    w_points = int(numpy.round(w_ / spacing))
    if w_points == 0: w_points = 1
    w_real_step = w_ / w_points

    for x_ in range(w_points + 1):
        x = x_ * w_real_step

        # Border width > 0 make lines to be clipped in x and y direction at DUT border.
        if border_width <= x <= w_ - border_width:
            retval.append(Containers.Line(x, border_width, spacing, x, h_ - border_width, spacing))

    return retval


def create_nmm_horizontal_lines(dut, spacing, border_width):
    """
    Chooses which function should be used for creating the evenly
    spaced horizontal lines.
    :param dut: tnt_dut object
    :param spacing: distance between two adjacent lines
    :param border_width: width of the edge area
    :return: list of containers.lines
    """
    if len(dut.svg_data()) > 0:
        return create_nmm_horizontal_lines_svg(dut, spacing, border_width)
    else:
        return create_nmm_horizontal_lines_rectangle(dut, spacing, border_width)


def create_nmm_horizontal_lines_svg(dut, spacing, border_width):
    """
    Create horizontal lines assuming the dut is rectangle and then clip them based
    on dut svg borders
    :param dut: tnt_dut object
    :param spacing: distance between two adjacent lines
    :param border_width: width of the edge area
    :return: list of clipped containers.lines
    """
    lines_all = create_nmm_horizontal_lines_rectangle(dut, spacing, border_width=0)
    return clip_lines_svg(dut, lines_all, border_width, 'analysis_region')


def create_nmm_horizontal_lines_rectangle(dut, spacing, border_width=0):
    retval = []

    w_ = dut.width
    h_ = dut.height
    h_points = int(numpy.round(h_ / spacing))
    if h_points == 0: h_points = 1
    h_real_step = h_ / h_points

    for y_ in range(h_points + 1):
        y = y_ * h_real_step

        # Border width > 0 make lines to be clipped in x and y direction at DUT border.
        if border_width <= y <= h_ - border_width:
            retval.append(Containers.Line(border_width, y, spacing, w_ - border_width, y, spacing))

    return retval


def create_center_points(dut, number_of_points, border_width):
    """
    Checks which function should be used for creating random center points
    :param dut: tnt_dut object
    :param number_of_points: number of random points
    :param border_width: width of the edge area
    :return: list of container.points created by correct grid creation function
    """
    if len(dut.svg_data()) > 0:
        return create_center_points_svg(dut, number_of_points, border_width)
    else:
        return create_center_points_rectangle(dut, number_of_points, border_width)


def create_center_points_svg(dut, number_of_points, border_width):
    """
    Create random points in center area. First assuming the dut is rectangle and
    then checking if the created point is in the center area of real dut.
    This is continued until number_of_points is reached
    :param dut: tnt_dut object
    :param number_of_points: wanted number of random points
    :param border_width: width of the edge area
    :return: list of containers.points
    """
    created_points = []
    while len(created_points) < number_of_points:
        # Create one random point that can be anywhere in the dut area
        points = create_center_points_rectangle(dut, number_of_points=1, border_width=0)
        point = points[0]
        # Check if the point is in wanted area and save if it is
        if is_point_in_area(point, 'center_area', dut, border_width):
            created_points.append(point)
    return created_points


def create_center_points_rectangle(dut, number_of_points, border_width):
    points = []

    w_ = dut.width - 2 * border_width
    h_ = dut.height - 2 * border_width
    for point in range(number_of_points):
        points.append(Containers.TouchAreaPoint(
            (numpy.random.rand(1)[0] * w_) + border_width,
            (numpy.random.rand(1)[0] * h_) + border_width,
            0,
            touch_area='center_area'
        ))

    return points


def create_edge_points(dut, points_per_edge, border_width):
    """
    Chooses the correct funtion to create random edge points
    :param dut: tnt_dut object
    :param points_per_edge: number of random points in each for edges
    :param border_width: width of the edge area
    :return: list of containers.points created by chosen function
    """
    if len(dut.svg_data()) > 0:
        return create_edge_points_svg(dut, points_per_edge, border_width)
    else:
        return create_edge_points_rectangle(dut, points_per_edge, border_width)


def create_edge_points_svg(dut, points_per_edge, border_width):
    """
    Creates defined number (points_per_edge) of points on all four edges. The first
    guess of random location is done by assuming the dut is rectangle. Then it is checked if
    the point really is in the edge area. This is repeated untill the number of points is reached
    :param dut: tnt_dut object
    :param points_per_edge: number of points per any of four edges
    :param border_width: width of the border area
    :return: list of containers.points
    """
    points = []
    if not border_width > 0.0:
        return points
    # Keep track on how many suitable points we have
    num_points = 0
    # Start with vertical borders
    w_ = border_width
    h_ = dut.height - 2 * border_width
    # Right vertical border
    while num_points < points_per_edge:
        point = Containers.TouchAreaPoint(
            (numpy.random.rand(1)[0] * w_),
            (numpy.random.rand(1)[0] * h_) + border_width,
            0,
            touch_area='edge_area'
            )
        if is_point_in_area(point, 'edge_area', dut, border_width):
            points.append(point)
            num_points += 1
    num_points = 0
    # Left vertical border
    while num_points < points_per_edge:
        point = Containers.TouchAreaPoint(
                dut.width - (numpy.random.rand(1)[0] * w_),
                (numpy.random.rand(1)[0] * h_) + border_width,
                0,
                touch_area='edge_area'
            )
        if is_point_in_area(point, 'edge_area', dut, border_width):
            points.append(point)
            num_points += 1
    num_points = 0
    # Move to horizontal borders
    w_ = dut.width - 2 * border_width
    h_ = border_width
    # Upper horizontal border
    notch_height = find_notch_height(dut)
    while num_points < points_per_edge:
        point = Containers.TouchAreaPoint(
                (numpy.random.rand(1)[0] * w_) + border_width,
                (numpy.random.rand(1)[0] * (h_ + notch_height)),
                0,
                touch_area='edge_area'
            )
        if is_point_in_area(point, 'edge_area', dut, border_width):
            points.append(point)
            num_points += 1
    num_points = 0
    # Lower horizontal border
    while num_points < points_per_edge:
        point = Containers.TouchAreaPoint(
                (numpy.random.rand(1)[0] * w_) + border_width,
                dut.height - (numpy.random.rand(1)[0] * h_),
                0,
                touch_area='edge_area'
            )
        if is_point_in_area(point, 'edge_area', dut, border_width):
            points.append(point)
            num_points += 1

    return points

def find_notch_height(dut):
    '''
    Finds out the notch height from dut by creating a vertical line in the middle of
    the dut and then clipping it and checking if start_y coordinate has changed
    (because it is clipped by the notch)
    :param dut: tnt_dut object (needs to have svg file defined)
    :return: height of the notch
    '''
    mid_point = dut.width/2
    start_x, end_x = mid_point, mid_point
    start_y, end_y = 0, dut.height
    filtered_points = dut.filter_lines([(start_x, start_y, end_x, end_y)], 'analysis_region', 0)
    return filtered_points[0][0][1] # start_y that would be the end of the notch

def create_edge_points_rectangle(dut, points_per_edge, border_width):
    points = []

    if border_width > 0.0:
        w_ = border_width
        h_ = dut.height - 2 * border_width

        for point in range(points_per_edge):
            points.append(Containers.TouchAreaPoint(
                (numpy.random.rand(1)[0] * w_),
                (numpy.random.rand(1)[0] * h_) + border_width,
                0,
                touch_area='edge_area'
            ))
            points.append(Containers.TouchAreaPoint(
                dut.width - (numpy.random.rand(1)[0] * w_),
                (numpy.random.rand(1)[0] * h_) + border_width,
                0,
                touch_area='edge_area'
            ))

        w_ = dut.width - 2 * border_width
        h_ = border_width

        for point in range(points_per_edge):
            points.append(Containers.TouchAreaPoint(
                (numpy.random.rand(1)[0] * w_) + border_width,
                (numpy.random.rand(1)[0] * h_),
                0,
                touch_area='edge_area'
            ))
            points.append(Containers.TouchAreaPoint(
                (numpy.random.rand(1)[0] * w_) + border_width,
                dut.height - (numpy.random.rand(1)[0] * h_),
                0,
                touch_area='edge_area'
            ))

    return points

def create_corner_points(dut, points_per_corner, border_width):
    """
    Chooses the function to create random corner points
    :param dut: tnt_dut_object
    :param points_per_corner: number of random points for each four corners
    :param border_width: width of the edge area
    :return: list of container.points created by correct grid creation function
    """
    if len(dut.svg_data()) > 0:
        return create_corner_points_svg(dut, points_per_corner, border_width)
    else:
        return create_corner_points_rectangle(dut, points_per_corner, border_width)


def create_corner_points_svg(dut, points_per_corner, border_width):
    """
    Creates defined number (points_per_corner) of points on all four corners. The first
    guess of random location is done by assuming the dut is rectangle. Then it is checked if
    the point is in the corner area. This is repeated until the number of points is reached
    :param dut: tnt_dut object
    :param points_per_corner: number of points per any of four corners
    :param border_width: width of the border area
    :return: list of containers.points
    """
    points = []

    if not border_width > 0.0:
        return points

    w_ = border_width
    h_ = border_width

    # Keep track on how many suitable points we have
    num_points = 0
    # Top right corner
    while num_points < points_per_corner:
        point = Containers.TouchAreaPoint(
            (numpy.random.rand(1)[0] * w_),
            (numpy.random.rand(1)[0] * h_),
            0,
            touch_area='corner_area'
            )
        if is_point_in_area(point, 'corner_area', dut, border_width):
            points.append(point)
            num_points += 1

    num_points = 0
    # Top left corner
    while num_points < points_per_corner:
        point = Containers.TouchAreaPoint(
            dut.width - (numpy.random.rand(1)[0] * w_),
            (numpy.random.rand(1)[0] * h_),
            0,
            touch_area='corner_area'
        )
        if is_point_in_area(point, 'corner_area', dut, border_width):
            points.append(point)
            num_points += 1

    num_points = 0
    # Bottom left corner
    while num_points < points_per_corner:
        point = Containers.TouchAreaPoint(
            (numpy.random.rand(1)[0] * w_),
            dut.height - (numpy.random.rand(1)[0] * h_),
            0,
            touch_area='corner_area'
        )
        if is_point_in_area(point, 'corner_area', dut, border_width):
            points.append(point)
            num_points += 1

    num_points = 0
    # Bottom right corner
    while num_points < points_per_corner:
        point = Containers.TouchAreaPoint(
            dut.width - (numpy.random.rand(1)[0] * w_),
            dut.height - (numpy.random.rand(1)[0] * h_),
            0,
            touch_area='corner_area'
        )
        if is_point_in_area(point, 'corner_area', dut, border_width):
            points.append(point)
            num_points += 1

    # Sorting points to be tapped in sensible order
    points.sort(key=lambda _point: (math.sqrt(_point.x ** 2 + _point.y ** 2)))
    return points


def create_corner_points_rectangle(dut, points_per_corner, border_width):
    points = []

    if border_width > 0.0:
        w_ = border_width
        h_ = border_width

        for point in range(points_per_corner):
            points.append(Containers.TouchAreaPoint(
                (numpy.random.rand(1)[0] * w_),
                (numpy.random.rand(1)[0] * h_),
                0,
                touch_area='corner_area'
            ))
            points.append(Containers.TouchAreaPoint(
                dut.width - (numpy.random.rand(1)[0] * w_),
                (numpy.random.rand(1)[0] * h_),
                0,
                touch_area='corner_area'
            ))
            points.append(Containers.TouchAreaPoint(
                (numpy.random.rand(1)[0] * w_),
                dut.height - (numpy.random.rand(1)[0] * h_),
                0,
                touch_area='corner_area'
            ))
            points.append(Containers.TouchAreaPoint(
                dut.width - (numpy.random.rand(1)[0] * w_),
                dut.height - (numpy.random.rand(1)[0] * h_),
                0,
                touch_area='corner_area'
            ))

    points.sort(key=lambda _point: (math.sqrt(_point.x ** 2 + _point.y ** 2)))
    return points
