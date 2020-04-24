import base64
import logging
import hashlib

from twisted.internet import reactor, endpoints, ssl
from twisted.web.resource import Resource, ForbiddenResource
from twisted.web.server import Site

import BridgeApplication
from BaseServerBridge import BaseBridge
import os


LOG = logging.getLogger("Twist-HTTP")


class ReadyPage(Resource):
    isLeaf = True

    def __init__(self, bridge):
        Resource.__init__(self)
        self._bridge = bridge

    def render_GET(self, request):
        return ForbiddenResource()

    def render_POST(self, request):
        BridgeApplication.READY = True
        return 'OK'


def fail(request, code, msg):
    request.setResponseCode(code)
    client_addr = request.getClientAddress()
    LOG.info("Failed to process request from %s:%d: code=%d, msg=%s"
             % (client_addr.host, client_addr.port, code, msg))
    return msg


class ZMQDataPage(Resource):
    isLeaf = True

    def __init__(self, bridge):
        Resource.__init__(self)
        self._bridge = bridge

    def render(self, request):
        if request.method != b'POST':
            return fail(request, 405, "Bad request method")

        content_length_str = request.getHeader("Content-Length")
        if content_length_str is None:
            return fail(request, 411, "Received bad request from %s" % self.client_address[0])

        content_length = int(content_length_str)
        # we _would_ use <= 0, but ZMQ itself actually uses 0 length "data"
        if content_length < 0:
            return fail(request, 400, "Bad Content-Length from %s" % self.client_address[0])

        # read the base64 encoded data
        b64_data = request.content.read(content_length)
        LOG.info("Received new request of %d bytes..." % len(b64_data))
        # decode our data
        zmq_data = base64.b64decode(b64_data)
        # now check for validity; if we're invalid, don't forward it.
        digest = hashlib.sha256(zmq_data).hexdigest()
        if digest != request.getHeader("X-Verify-Hash"):
            return fail(request, 500, "Hash check failed.")

        # then forward it onto the ZMQ app
        self._bridge.zmq_bridge.transfer_data_to_app(zmq_data)
        LOG.info("Forwarded %d bytes..." % len(zmq_data))
        return 'OK'


class BridgePage(Resource):
    def render(self, request):
        return fail(request, 400, "No action specified.")


class Bridge(BaseBridge):
    def __init__(self, zmq_bridge, bind_address: str, bind_port: int):
        super().__init__(True)

        self.zmq_bridge = zmq_bridge
        self._twisted_root = BridgePage()
        self._twisted_root.putChild(b'zmq', ZMQDataPage(self))
        self._twisted_root.putChild(b'ready', ReadyPage(self))

        self._twisted_server = Site(self._twisted_root)

        local_path = os.path.abspath(__file__)
        ssl_context = ssl.DefaultOpenSSLContextFactory(
            os.path.join(local_path, 'privkey.pem'),
            os.path.join(local_path, 'cacert.pem'),
        )

        self._twisted_endpoint = endpoints.SSL4ServerEndpoint(reactor, bind_port, ssl_context, interface=bind_address)
        LOG.info("Created Twisted endpoint on %s:%d" % (bind_address, bind_port))

    def tick_server(self):
        LOG.info("Starting Twisted server...")
        self._twisted_endpoint.listenSSL(self._twisted_server)
