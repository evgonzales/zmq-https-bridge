import base64
import http.server
import logging

from BaseServerBridge import BaseBridge


LOG = logging.getLogger("HTTP")
BRIDGE_INSTANCE = None


@DeprecationWarning
class BridgeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        self.server.get_context().set_ready(True)
        self.send_response(200)
        self.end_headers()

    def do_POST(self) -> None:
        content_length_str = self.headers.get("Content-Length")
        if content_length_str is None:
            self._failed(411, "Received bad request from %s" % self.client_address[0])
            return

        content_length = int(content_length_str)
        # we _would_ use <= 0, but ZMQ itself actually uses 0 length "data"
        if content_length < 0:
            self._failed(400, "Bad Content-Length from %s" % self.client_address[0])
            return

        LOG.info("Received new request of %d bytes" % content_length)
        zmq_data = base64.b64decode(self.rfile.read(content_length))
        # "".join() technique borrowed from https://stackoverflow.com/a/12073686
        LOG.debug("Sample output: %s", "".join(map(chr, zmq_data)))
        # transfer zmq_data to ZMQBridge
        self.send_response(200)
        self.end_headers()

    def _failed(self, status_code, msg):
        LOG.warning(msg)
        self.send_error(status_code)
        self.end_headers()


@DeprecationWarning
class Bridge(BaseBridge):
    def __init__(self, bridge_context, bind_address: str, bind_port: int, destination: str, we_are_hosting: bool):
        # create and bind our HTTPServer to the given address
        self._http_server = http.server.HTTPServer((bind_address, bind_port), BridgeRequestHandler)
        # copy our get_context function to _http_server to allow us to 'pass' a parameter
        self._http_server.get_context = self.get_context
        LOG.info("HTTP server created and bound to: http://%s:%d" % (bind_address, bind_port))

        # set our running state to True
        super().__init__(bridge_context, True)
        bridge_context.init_http_bridge(self)

        global BRIDGE_INSTANCE
        BRIDGE_INSTANCE = self

    def tick_server(self):
        LOG.info("HTTP server thread started")
        while self.is_running():
            LOG.info("Awaiting request...")
            self._http_server.handle_request()
            LOG.info("Finishing handling request")
