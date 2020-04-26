import base64
import hashlib
import logging

from twisted.internet import reactor, ssl
from twisted.internet.defer import succeed
from twisted.internet.endpoints import HostnameEndpoint
from twisted.web.client import Agent, ProxyAgent
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer, IPolicyForHTTPS
from txzmq import ZmqFactory, ZmqRouterConnection, ZmqDealerConnection, ZmqEndpoint, ZmqEndpointType
from zope.interface import implementer

from BaseServerBridge import BaseBridge

LOG = logging.getLogger("ZMQ")
USE_HTTPS_PROXY = False
PROXY_HOST = "10.0.0.208"
PROXY_PORT = 8888


@implementer(IPolicyForHTTPS)
class DisableSSLVerificationFactory(object):
    def __init__(self):
        pass

    def creatorForNetloc(self, hostname, port):
        return ssl.CertificateOptions(verify=False)


class Bridge(BaseBridge):
    def __init__(self, address: str, port: int, destination: str, is_app_hosting: bool):
        self._address = address
        self._port = port
        self._destination = destination
        self._is_app_hosting = is_app_hosting
        self._zmq_factory = ZmqFactory()

        if is_app_hosting:
            zmq_socket_class = ZmqDealerConnection
            zmq_endpoint = ZmqEndpoint(ZmqEndpointType.connect, "tcp://%s:%d" % (address, port))
            LOG.info("Configured txZMQ for connecting to application "
                     "- connected to tcp://%s:%d" % (address, port))
        else:
            zmq_socket_class = ZmqRouterConnection
            zmq_endpoint = ZmqEndpoint(ZmqEndpointType.bind, "tcp://%s:%d" % (address, port))
            LOG.info("Configured txZMQ for application connecting to us "
                     "- socket bound to tcp://%s:%d" % (address, port))

        self._zmq_socket = zmq_socket_class(self._zmq_factory, zmq_endpoint)
        self._zmq_socket_identity = None

        LOG.info("Initializing socket and agent")
        if USE_HTTPS_PROXY:
            self._twisted_agent = ProxyAgent(HostnameEndpoint(reactor, PROXY_HOST, PROXY_PORT), reactor)
            LOG.warning("Agent is using HTTP proxy for outbound work!")
        else:
            self._twisted_agent = Agent(reactor, contextFactory=DisableSSLVerificationFactory())

        def post_data(*zmq_data_recv):
            self._zmq_socket_identity = zmq_data_recv[0]
            data = zmq_data_recv[-1]
            LOG.info("Received %d bytes of data" % len(data))
            data_hash = hashlib.sha256(data).hexdigest()
            b64_data = base64.b64encode(data)
            request = self._twisted_agent.request(
                b'POST',
                (destination + "/zmq").encode(),
                Headers({
                    'User-Agent': ['ZMQ-HTTP-Bridge-Agent'],
                    'X-Verify-Hash': [data_hash]
                }),
                bodyProducer=StringProducer(b64_data)
            )

            def handle_twisted_error(fail):
                LOG.info("have %d errors", len(fail.value.reasons))
                LOG.error("%s", str(fail.value.reasons[0]))

            request.addErrback(handle_twisted_error)
            request.addCallback(lambda ignored: LOG.info("Request completed."))

            LOG.info("Forwarded data to destination (hash preview: %s)" % data_hash[0:8])

        self._zmq_socket.gotMessage = post_data

    def transfer_data_to_app(self, data):
        LOG.info("Sending bytes to client...")
        LOG.debug("data=%s", data.decode())
        if self._is_app_hosting:
            self._zmq_socket.socket.send_multipart([b'', data])
        else:
            self._zmq_socket.socket.send_multipart([self._zmq_socket_identity, b'', data])
        LOG.info("Sent.")


@implementer(IBodyProducer)
class StringProducer:
    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass
