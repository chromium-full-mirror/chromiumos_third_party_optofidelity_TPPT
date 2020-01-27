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
from functools import wraps
import logging
import numpy as np
import threading

log = logging.getLogger(__name__)


class NodeException(Exception):
    def __init__(self, title, http_code=500, messages=None):
        self.title = title
        self.http_code = http_code
        self.messages = messages if messages is not None else []


def _content_type_unpack(something):
    """
    Unpack return value
    :return: tuple of (response code, response payload, response headers)
    """
    if isinstance(something, tuple):
        if len(something) == 1:
            return None, something[0], None
        elif len(something) == 2:
            return None, something[0], something[1]
        elif len(something) == 3:
            return something
        else:
            raise NodeException("Too many values in tuple")
    else:
        return None, something, None


def _content_type_pack(response_code, response_type, response_payload, response_headers):
    if response_code is not None:
        return response_code, response_type, response_payload, response_headers
    elif response_headers is not None:
        return response_type, response_payload, response_headers
    elif response_type is not None:
        return response_type, response_payload
    else:
        return response_payload


def json_out(some_function):
    @wraps(some_function)
    def wrapper(cls, *args, **kwargs):
        code, rv, headers = _content_type_unpack(some_function(cls, *args, **kwargs))
        return _content_type_pack(code, "application/json", json.dumps(rv).encode("utf-8"), headers)

    return wrapper


class Node:
    root = None

    def __init__(self, name):
        self.name = name

        self.children = {}
        self.parent = None

        self._api_lock = threading.Lock()

    def add_child(self, node):

        if node is None:
            print(node)

        self.children[node.name] = node
        node.parent = self

    def find_child_with_path(self, path):
        # TODO: path is misleading. Is this function needed in addition to find_from()?
        for child in self.children.values():
            if child.name == path:
                return child
        raise NodeException("Child not found", 404)

    @json_out
    def tnt2_info(self):
        """
        Returns node information in tnt2 supported format.
        This is needed for sequence generator support.
        :return:
        """

        children = []
        if len(self.children) > 0:
            lst = []
            for c_name in self.children:
                c = self.children[c_name]
                # If the child has the _kind attribute report that, otherwise 'Unknown'
                try:
                    c_kind = c._kind
                except AttributeError:
                    c_kind = 'Unknown'

                children.append({"name": c_name, "type": c.__class__.__name__, "kind": c_kind})

        #

        links = []
        f_get = [('get', p[4:]) for p in dir(self.__class__) if p[:4] == "get_"]
        f_put = [('put', p[4:]) for p in dir(self.__class__) if p[:4] == "put_"]
        f_post = [('post', p[5:]) for p in dir(self.__class__) if p[:4] == "post_"]
        functions = f_get + f_put + f_post

        # create href links
        pth = ""
        n = self
        while n is not None:
            pth = "/" + n.name + pth
            n = n.parent
        pth = "http://127.0.0.1:8000" + pth + "/"

        for t, f in functions:
            links.append({"method": t.upper(), "href": pth + f})

        info = {self.name: children, "_links": links}

        #

        property_names = [p for p in dir(self.__class__) if isinstance(getattr(self.__class__, p), property)]
        if len(property_names) > 0:
            properties = {}
            for name in property_names:
                try:
                    if name[0] != "_":
                        value = getattr(self, name)
                        if isinstance(value, np.matrix):
                            value = [[float(v) for v in a] for a in value.A]
                        elif issubclass(value.__class__, Node):
                            # Node objects are not json serializable, use the name of the Node as value instead
                            value = value.name

                        properties[name] = value
                except Exception as e:
                    log.error("could not read property {} of {} : {}".format(name, self.name, e))

            info["properties"] = properties

        return info

    @json_out
    def get_relations(self):
        """
        Moved from default info to here because breaks TnT2 compatibility
        :return:
        """
        parent_name = self.parent.name if self.parent is not None else ""
        object_parent_name = self.object_parent.name if self.object_parent is not None else ""
        info = {'name': self.name, 'parent': parent_name, 'connection': object_parent_name}
        return info

    @json_out
    def put_properties(self, **kwargs):
        fail = False
        for name in kwargs:

            #if self.private_property(name):
            #    log.debug("{} : skip set private property {}".format(self.name, name))
            #    continue
            value = kwargs[name]
            try:
                setattr(self, name, value)
                log.info("{} : set property {} = {}".format(self.name, name, value))
            except Exception as e:
                log.exception(e)  # Better to get information about original exception
                log.warning("could not set property '{}' of '{}' to {}", name, self.fullname(), value)
                fail = True

        if fail:
            raise Exception("setting property failed")
        else:
            pass
            #self.save()

        return ""

    @json_out
    def get_properties(self):
        p = self.__properties()
        return p

    def fullname(self):
        parts = []
        node = self
        while node:
            parts.append(node.name)
            node = node.parent
        name = ".".join(parts[::-1])
        return name

    def __properties(self):
        properties = {}

        def map_dict(d):
            ret = {}
            for name, value in d.items():
                if isinstance(value, dict):
                    ret[name] = map_dict(value)
                else:
                    ret[name] = {"value": str(value), "type": value.__class__.__name__}
            return ret

        property_names = [p for p in dir(self.__class__) if isinstance(getattr(self.__class__, p), property)]
        for name in property_names:
            if name[0] == "_":
                continue
            try:
                value = getattr(self, name)
                if isinstance(value, dict):
                    properties[name] = map_dict(value)
                else:
                    properties[name] = {"value": str(value), "type": value.__class__.__name__}
            except Exception as e:
                log.error("could not read property {} of {} : {}".format(name, self.name, e))

        return properties

    @staticmethod
    def find(name):
        """
        Find Node with name recursively from whole tree
        :param name: name of the Node to find
        :return: found Node or None
        """
        if Node.root is None:
            return None
        found = Node.find_from(Node.root, name)
        return found

    @staticmethod
    def find_from(from_node, name: str):
        """
        Find Node with name recursively using from_node as root
        :param name: name of the Node to find
        :return: found Node or None
        """
        if from_node.name == name:
            return from_node
        if hasattr(from_node, 'children'):
            for child in from_node.children.values():
                found = Node.find_from(child, name)
                if found:
                    return found
        return None
