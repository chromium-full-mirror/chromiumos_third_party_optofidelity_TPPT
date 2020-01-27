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
import cgi
import http.server
import json
import logging
import socketserver
from urllib.parse import urlparse, parse_qsl, unquote

log = logging.getLogger(__name__)

from .node import Node, NodeException


class RequestHandler(http.server.BaseHTTPRequestHandler):

    def _to_parts(self, path):
        if path[0] == "/":
            path = path[1:]
        return [unquote(part, "utf-8") for part in path.split("/")]

    def do_PUT(self):
        parsed = urlparse(self.path)
        parts = self._to_parts(parsed.path)
        self.respond(parts, 'put')

    def do_POST(self):
        parsed = urlparse(self.path)
        parts = self._to_parts(parsed.path)
        self.respond(parts, 'post')

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = self._to_parts(parsed.path)
        self.respond(parts, 'get')

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = self._to_parts(parsed.path)
        self.respond(parts, 'delete')

    def do_OPTIONS(self):
        parsed = urlparse(self.path)
        parts = self._to_parts(parsed.path)
        node, part = self._find_path(parts)
        part = part[0]
        allowed_verbs = []
        if node is not None:
            for verb in ["get", "put", "post", "delete"]:
                try:
                    getattr(node, verb + "_" + part)
                    allowed_verbs.append(verb.upper())
                except AttributeError:
                    pass
        if allowed_verbs:
            allowed_verbs.append("OPTIONS")
            self._respond(200, headers={"Access-Control-Allow-Methods": ", ".join(allowed_verbs)})
        else:
            self._respond(404)

    def _get_raw_content(self):
        if 'Content-Length' in self.headers:
            content_length = int(self.headers['Content-Length'])
            return self.rfile.read(content_length)

    def _get_content(self):
        if 'Content-Type' in self.headers and 'Content-Length' in self.headers:
            content_type, pdict = cgi.parse_header(self.headers['Content-Type'])
            content_length = int(self.headers['Content-Length'])

            if content_type == 'multipart/form-data':
                if 'boundary' in pdict and isinstance(pdict['boundary'], str):
                    pdict['boundary'] = pdict['boundary'].encode()
                log.debug('Parse multipart/form-data for params %s', pdict)
                parsed = cgi.parse_multipart(self.rfile, pdict)
                parsed = self._strip_empty_lists(parsed)
                parsed = self._extract_json_data(parsed)
                return parsed
            elif content_type == 'application/x-www-form-urlencoded':
                post_data = self.rfile.read(content_length)
                return parse_qsl(post_data, keep_blank_values=True)
            elif content_type == 'application/json':
                post_data = self.rfile.read(content_length)
                return json.loads(post_data.decode())
            elif content_type == "audio/x-wav":
                post_data = self.rfile.read(content_length)
                return post_data

    @staticmethod
    def _strip_empty_lists(data):
        def strip_list(value):
            if isinstance(value, list) and len(value) == 1:
                return value[0]
            return value
        return {k: strip_list(v) for k, v in data.items()}

    @staticmethod
    def _extract_json_data(data):
        # Other params can be embedded as JSON to have typed data:
        typed_data = {}
        if 'json_data' in data:
            typed_data = json.loads(data['json_data'].decode('utf-8'))
            del data['json_data']
        return {**data, **typed_data}

    def _parse_query_string(self):
        parsed = urlparse(self.path)
        query_parts = parse_qsl(parsed.query)
        params = {}
        for name, value in query_parts:
            if value == "true" or value == "True":
                value = True
            elif value == "false" or value == "False":
                value = False
            else:
                try:
                    v = float(value)
                    value = v
                except:
                    pass

            params[name] = value
        return params

    def safe_call(self, instance, handler, *args):
        try:
            thread_safe = handler.__thread_safe
        except:
            thread_safe = False

        if thread_safe:
            v = self.call(handler, *args)
        else:
            with instance._api_lock:
                v = self.call(handler, *args)
        return v

    def safe_call_no_response(self, instance, handler, *args):
        """
        Call node method that does not send response (e.g. multipart HTTP request).
        :param instance: Node object whose method to call.
        :param handler: Node method that is called.
        :param args: Arguments to handler.
        :return: Return value of handler.
        """
        try:
            thread_safe = handler.__thread_safe
        except:
            thread_safe = False

        if thread_safe:
            v = handler(*args)
        else:
            with instance._api_lock:
                v = handler(*args)
        return v

    def call(self, handler, *args):
        response_code = 200
        response_content_type = None
        response_data = None
        response_headers = None

        request_content = None
        try:
            if not hasattr(handler, 'decodes'):
                request_content = self._get_content()
                params = self._parse_query_string()
                if request_content:
                    if not isinstance(request_content, dict):
                        request_content = {"value": request_content}
                    params.update(request_content)
                out = handler(*args, **params)
                if not isinstance(out, tuple):
                    raise Exception("Internal callback did not return tuple")
            else:
                request_content = self._get_raw_content()
                out = handler(*args, request_content)

            if len(out) == 1:
                response_data = out,
            elif len(out) == 2:
                response_content_type, response_data = out
            elif len(out) == 3:
                response_content_type, response_data, response_headers = out
            elif len(out) == 4:
                response_code, response_content_type, response_data, response_headers = out

        except NodeException as e:
            log.exception("Request could not be completed: %s. HTTP payload: %s", e.messages, request_content)
            response_code = e.http_code
            response_content_type = "application/json"
            response_data = json.dumps({"status": "Request processing failed", "message": e.title,
                               "details": e.messages}).encode("utf-8")
        except TypeError as e:
            log.exception("Bad request due to TypeError (missing parameters?). HTTP payload: %s", request_content)
            response_code = 400
            response_content_type = "application/json"
            response_data = json.dumps({"status": "Request processing failed", "message": "Bad request",
                               "details": [str(e)]}).encode("utf-8")
        except Exception as e:
            log.exception("Uncaught exception caused internal error). HTTP payload: %s", request_content)
            response_code = 500
            response_content_type = "application/json"
            response_data = json.dumps({"status": "Request processing failed", "message": "Internal server error",
                               "details": [str(e)]}).encode("utf-8")
        return response_code, response_content_type, response_data, response_headers

    def _find_path(self, parts):
        #
        # Traverse tree with parts
        #
        node = Node.root

        while len(parts):
            part = parts[0]
            if node is None or node.name != part:
                break
            parts = parts[1:]
            if len(parts) == 0:
                break
            part = parts[0]
            try:
                node = node.find_child_with_path(part)
            except:
                break
        return node, parts

    def respond(self, parts, scheme):
        #
        # Traverse tree with parts
        #
        log.debug("Handling HTTP %s for %s", scheme.upper(), "/".join(parts))

        node, parts = self._find_path(parts)
        if node is not None and len(parts) > 0:
            f = None
            path_handler = None
            is_multipart = False

            try:
                f = getattr(node, scheme + "_" + parts[0])
                is_multipart = getattr(f, "multipart", False)

            except AttributeError:
                try:
                    path_handler = getattr(node, "handle_path")
                except AttributeError:
                    pass

            if f is not None:
                log.debug("calling function {} of {}".format(parts[0], node.name))

                # Let multipart functions handle their own response
                if is_multipart:
                    self.safe_call_no_response(node, f, self)
                    return
                else:
                    response_code, datatype, data, extra_headers = self.safe_call(node, f)

            elif path_handler is not None:
                log.debug("path handler {} : {}".format(node.name, ".".join(parts)))
                response_code, datatype, data, extra_headers = self.safe_call(node, path_handler, scheme, "/".join(parts))

            else:
                response_code = 404
                datatype = "text/plain"
                data = "Not found".encode()
                extra_headers = None

                log.warning("found path until {} and remain part {} but did not find goal".format(node.name, ".".join(parts)))

            self._respond(response_code, datatype, data, extra_headers)
            return

        elif node is not None:
            try:
                f = getattr(node, scheme + "_self")
            except:
                f = None

            response_code = 200
            extra_headers = None
            if f is not None:
                response_code, datatype, data, extra_headers = self.safe_call(node, f)
            else:
                datatype, data = node.tnt2_info()
            self._respond(response_code, datatype, data, extra_headers)
            return

        self._respond(404)

    def _respond(self, response_code, content_type=None, data=None, headers=None):
        self.send_response(response_code)
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Expose-Headers", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Origin", "*")
        if "Access-Control-Request-Headers" in self.headers:
            self.send_header("Access-Control-Allow-Headers", self.headers["Access-Control-Request-Headers"])


        if content_type is not None:
            self.send_header("Content-Type", content_type)
            content_length = len(data) if data is not None else 0
            self.send_header("Content-Length", content_length)
        if headers is not None:
            for header, header_value in headers.items():
                self.send_header(header, header_value)
        self.end_headers()
        if data is not None:
            self.wfile.write(data)

    def log_message(self, format, *args):
        """Log an arbitrary message.

        This is used by all other logging functions.  Override
        it if you have specific logging wishes.

        The first argument, FORMAT, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).

        The client ip and current date/time are prefixed to
        every message.

        """
        log.debug("%s - %s" % (self.address_string(), format%args))


class DryRunThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):

    def __init__(self, addr):
        self.allow_reuse_address = 1

        socketserver.ThreadingTCPServer.__init__(self, addr, RequestHandler)


