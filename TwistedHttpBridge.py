import base64
import hashlib
import logging

from twisted.internet import reactor, endpoints, ssl
from twisted.web.resource import Resource
from twisted.web.server import Site

from BaseServerBridge import BaseBridge

LOG = logging.getLogger("Twist-HTTP")


def fail(request, code, msg):
    request.setResponseCode(code)
    client_addr = request.getClientAddress()
    LOG.debug("Failed to process request from %s:%d: code=%d, msg=%s"
              % (client_addr.host, client_addr.port, code, msg))
    return msg


class ZMQDataPage(Resource):
    isLeaf = True

    def __init__(self, bridge):
        Resource.__init__(self)
        self._bridge = bridge

    def render(self, request):
        LOG.info("Handling new request...")
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
        LOG.debug("b64_data=%s" % b64_data)
        # decode our data
        zmq_data = base64.b64decode(b64_data)
        # now check for validity; if we're invalid, don't forward it.
        digest = hashlib.sha256(zmq_data).hexdigest()
        remote_digest = request.getHeader("X-Verify-Hash")
        if digest != remote_digest:
            return fail(request, 500, "Hash check failed (%s != %s)" % (digest[0:8], remote_digest[0:8]))

        # then forward it onto the ZMQ app
        self._bridge.zmq_bridge.transfer_data_to_app(zmq_data)
        LOG.info("Forwarded %d bytes..." % len(zmq_data))
        return b'OK'


class BridgePage(Resource):
    def render(self, request):
        return fail(request, 400, "No action specified.")


class Bridge(BaseBridge):
    def __init__(self, zmq_bridge, bind_address: str, bind_port: int):
        super().__init__(True)

        self.zmq_bridge = zmq_bridge
        self._twisted_root = BridgePage()
        self._twisted_root.putChild(b'zmq', ZMQDataPage(self))

        self._twisted_server = Site(self._twisted_root)

        ssl_context = ssl.DefaultOpenSSLContextFactory(
            'bridge-ssl.key',
            'bridge-ssl.pem'
        )

        self._twisted_endpoint = endpoints.SSL4ServerEndpoint(reactor, bind_port, ssl_context, interface=bind_address)
        self._twisted_endpoint.listen(self._twisted_server)
        LOG.info("Created HTTPS endpoint on %s:%d" % (bind_address, bind_port))
