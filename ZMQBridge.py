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


# helper class to bypass SSL verification due to self-signed certificates
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

        # if the ZMQ app is binding and hosting the server, we need to connect to that instead
        if is_app_hosting:
            zmq_socket_class = ZmqDealerConnection
            zmq_endpoint = ZmqEndpoint(ZmqEndpointType.connect, "tcp://%s:%d" % (address, port))
            LOG.info("Configured txZMQ for connecting to application "
                     "- connected to tcp://%s:%d" % (address, port))
        else:
            # otherwise, bind to the address/port and have them connect to us
            zmq_socket_class = ZmqRouterConnection
            zmq_endpoint = ZmqEndpoint(ZmqEndpointType.bind, "tcp://%s:%d" % (address, port))
            LOG.info("Configured txZMQ for application connecting to us "
                     "- socket bound to tcp://%s:%d" % (address, port))

        self._zmq_socket = zmq_socket_class(self._zmq_factory, zmq_endpoint)
        # store the socket identity of the client; we need it to send data back to the local ZMQ app
        self._zmq_socket_identity = None

        LOG.debug("Initializing socket and agent")
        # check if we want to use an HTTPS proxy; useful for Fiddler
        if USE_HTTPS_PROXY:
            self._twisted_agent = ProxyAgent(HostnameEndpoint(reactor, PROXY_HOST, PROXY_PORT), reactor)
            LOG.warning("Agent is using HTTP proxy for outbound work!")
        else:
            # otherwise, use the standard Agent with a nulled SSL verification process, since self-signed certificates
            # fail the connection process entirely
            self._twisted_agent = Agent(reactor, contextFactory=DisableSSLVerificationFactory())

        # setup auto-POST method for our socket
        def post_data(*zmq_data_recv):
            self._zmq_socket_identity = zmq_data_recv[0]
            data = zmq_data_recv[-1]
            LOG.debug("Received %d bytes of data" % len(data))
            # hash and base64 our data for validation and transportation
            data_hash = hashlib.sha256(data).hexdigest()
            b64_data = base64.b64encode(data)
            # POST it to the remote server
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
                # print out _all_ errors, since Twisted doesn't provide all exceptions
                for error in fail.value.reasons:
                    LOG.error("%s", str(error))

            request.addErrback(handle_twisted_error)
            request.addCallback(lambda ignored: LOG.debug("Request completed."))
            LOG.info("Forwarded data to destination (hash preview: %s)" % data_hash[0:8])

        self._zmq_socket.gotMessage = post_data

    def transfer_data_to_app(self, data):
        LOG.info("Sending bytes to client...")
        LOG.debug("data=%s", data.decode())
        # if the app is hosting, then we need to send an empty delimiter frame followed by our data
        if self._is_app_hosting:
            self._zmq_socket.socket.send_multipart([b'', data])
        else:
            # otherwise, we need to send the socket identity, empty frame, and then our data
            self._zmq_socket.socket.send_multipart([self._zmq_socket_identity, b'', data])


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
