import http.client
import http.server
import json
import socketserver

from . import model


class RequestHandler(http.server.BaseHTTPRequestHandler):
    def return_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data))

    def return_error(self, message):
        self.return_json({"error": message})

    def do_GET(self):
        self.return_json(self.server.model.labels)

    def do_POST(self):
        if (
                ("Content-Length" not in self.headers) or
                ("Content-Type" not in self.headers)):
            return self.send_response(400)

        nb = self.headers["Content-Length"]
        if not nb.isdigit():
            return self.send_response(400)

        nb = int(nb)
        if nb < 1:
            return self.send_response(400)

        body = self.rfile.read(nb)
        if self.headers["Content-Type"] != "application/json":
            return self.send_response(400)

        # read in json data
        jdata = json.loads(body.decode('ascii'))
        if 'input' not in jdata or not isinstance(jdata['input'], list):
            return self.send_response(400)

        # parse input
        input_array = numpy.array(jdata['input'])

        # invoke model
        with self.server.model_lock:
            output_array = self.model.run(input_array)

        # return result
        self.return_json(json.dumps(output_array.tolist())


class TFLiteModelServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, handler, model):
        super(TFLiteModelServer, self).__init__(address, handler)
        self.model = model
        self.model_lock = threading.Lock()

    def run(self):
        self.serve_forever()


server = TFLiteModelServer(
    ("", 8000),
    RequestHandler,
    model)
