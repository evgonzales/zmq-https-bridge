import logging
import sys
import threading
import time

from twisted.internet import reactor

import TwistedHttpBridge
import ZMQBridge

READY = False
LOG = logging.getLogger("BridgeMain")


def main():
    if len(sys.argv) <= 3:
        print("usage: %s <zmq bind address> <http bind address> <destination> [is-app-hosting]")
        print("\t<zmq bind address>: The address for the bridge's ZMQ listener to bind to. ZMQ applications should")
        print("\t\tuse this as their destination to run their data through the bridge. This parameter becomes the")
        print("\t\ttarget server to talk with if specified.")
        print("\t<http bind address>: The address for the bridge's HTTP server to bind to. The other bridge should")
        print("\t\tuse this as its <destination> parameter.")
        print("\t<destination>: The destination for any data received from the local ZMQ application. Must be HTTP(S).")
        print("\t[is-app-hosting]: If \"true\", then we assume the app is hosting and thus, we must connect to it")
        print("\t\trather than the app connecting to us.")
        return

    logging.basicConfig(level=logging.DEBUG, format="%(name)-12s: [%(levelname)-8s] %(message)s")

    # parse CLI options given
    zmq_addr, zmq_port = split_addr_port(sys.argv[1])
    LOG.info("Parsed ZMQ address: %s:%d" % (zmq_addr, zmq_port))

    http_bind_addr, http_bind_port = split_addr_port(sys.argv[2])
    LOG.info("Parsed HTTP binding address: %s:%d" % (http_bind_addr, http_bind_port))

    destination = sys.argv[3]
    # double check for HTTPS
    if not destination.startswith("https"):
        LOG.warning("INSECURE PROTOCOL: Destination is NOT using HTTPS.")
    LOG.info("Destination: %s" % destination)

    # then check to see if the ZMQ application is the one binding or if we're binding
    binding = len(sys.argv) > 4 and sys.argv[4] == "true"
    if binding:
        LOG.info("Configured for connecting to the given ZMQ address")

    # create our bridges
    zmq_bridge = ZMQBridge.Bridge(zmq_addr, zmq_port, destination, binding)
    http_bridge = TwistedHttpBridge.Bridge(zmq_bridge, http_bind_addr, http_bind_port)

    # create two threads; could be improved on by using Twisted's reactor-based stuff
    zmq_thread = threading.Thread(target=zmq_bridge.tick_server, args=(), daemon=True)
    http_thread = threading.Thread(target=http_bridge.tick_server, args=(), daemon=True)

    # start up the two new threads
    zmq_thread.start()
    http_thread.start()

    # wait for ZMQ and HTTP server to get ready
    time.sleep(1)

    # run Twisted - this blocks until Twisted ends
    reactor.run()

    # wait until each thread dies at this point
    try:
        while zmq_thread.is_alive() and http_thread.is_alive():
            zmq_thread.join(1)
            http_thread.join(1)
    except KeyboardInterrupt:
        LOG.info("Received KeyboardInterrupt - terminating.")
        exit(0)


def split_addr_port(input_combo: str) -> (str, int):
    splitted = input_combo.split(":", 1)
    return splitted[0].strip(), int(splitted[1])


if __name__ == "__main__":
    main()
