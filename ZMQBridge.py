import base64
import hashlib
import logging
import select
import socket
import time

import requests
from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer

import BridgeApplication
from BaseServerBridge import BaseBridge

LOG = logging.getLogger("ZMQ")


class Bridge(BaseBridge):
    def __init__(self, address: str, port: int,
                 destination: str, is_app_hosting: bool):
        super().__init__(True)
        # initialize a basic TCP socket for connecting to the ZMQ application
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # initialize our state as being unbounded, disconnected, and invalid
        self._is_bound = False
        self._connected = False
        self._valid = False

        self._address = address
        self._port = port
        self._is_app_hosting = is_app_hosting
        self._destination = destination

    def tick_server(self):
        LOG.info("ZMQ socket thread started, awaiting ZMQ app to connect")

        # only return to this loop if connection drops
        while self.is_running():
            # determine how to handle our connection to the ZMQ application
            if self._is_app_hosting:
                # wait for the other bridge to notify that its ready to connect
                LOG.info("Waiting for ready notice...")
                while not BridgeApplication.READY:
                    time.sleep(1)
            else:
                # otherwise, we're waiting for the ZMQ application to connect to us
                LOG.info("Configured for app to connect to us - waiting connection...")
                # prevent accidentally rebinding
                if not self._is_bound:
                    self._socket.bind((self._address, self._port))
                    self._is_bound = True
                self._socket.listen()
                # store our old server socket somewhere, in case if the ZMQ connection dies
                self._socket, _ = self._socket.accept()  # bad.
                self._connected = True  # avoid re-connect()ing under transfer_data_to_app
                LOG.info("Received connection, notifying remote that we're ready...")
                requests.post(self._destination + "/ready")

            # now begin our core loop
            while self._valid:
                zmq_data = self._socket.recv(1024)
                # encode and then digest the data for verification
                encoded = base64.b64encode(zmq_data)
                digest = hashlib.sha256(zmq_data).hexdigest()
                headers = {'User-Agent': 'ZMQ-HTTP-Bridge', 'X-Verify-Hash': digest}
                # POST the data to the remote server with our headers
                requests.post(self._destination + "/zmq", data=encoded, headers=headers)
                LOG.info("Forwarded data.")

    def transfer_data_to_app(self, data: bytes):
        LOG.info("Sending %d bytes to client..." % len(data))

        # connect now - for some reason, if we connect any earlier, ZMQ(? need to investigate what's going on)
        # will determine the socket as dead after not responding - is there a heartbeat that needs to be sent?
        if not self._connected:
            self._socket.connect((self._address, self._port))
            self._connected = True

        self._socket.send(data)


@implementer(IBodyProducer)
class StringProducer:
    def __init__(self, body):
        self._body = body
        self._len = len(body)

    def startProducing(self, consumer):
        consumer.write(self._body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass
