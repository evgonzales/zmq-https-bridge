import logging
from optparse import OptionParser
from twisted.internet import reactor

import multiprocessing_logging
import TwistedHttpBridge
import ZMQBridge
import BridgeInjector

logging.basicConfig(filename="zmq-https-bridge.log", filemode="a",
                    level=logging.INFO, format="%(name)-12s @ %(asctime)s: [%(levelname)-8s] %(message)s",
                    datefmt='%m/%d/%Y %I:%M:%S %p')
multiprocessing_logging.install_mp_handler()


def main():
    LOG = logging.getLogger("BridgeMain")

    usage = "usage: %s <zmq bind address> <http bind address> <destination> [is-app-hosting]"
    parser = OptionParser(usage=usage)
    parser.add_option("-z", "--zmq-bind-addr", dest="zmq_bind_address", help="The address for the bridge's ZMQ "
                                                                             "listener to bind to. ZMQ applications "
                                                                             "should use this as their destination "
                                                                             "to run their data through the bridge. "
                                                                             "This parameter becomes the target "
                                                                             "server to talk with if specified.")
    parser.add_option("-H", "--http-bind-addr", dest="http_bind_address", help="The address for the bridge's HTTP "
                                                                               "server to bind to. The other "
                                                                               "bridge should use this as its "
                                                                               "\"destination\" parameter.")
    parser.add_option("-d", "--destination", dest="destination", help="The destination for any data received from the "
                                                                      "local ZMQ application. Must be HTTP(S).")
    parser.add_option("-i", "--inject", dest="inject", help="If specified, the bridge will inject itself into the "
                                                            "source code of the specified Python application.",
                                                            default="")
    parser.add_option("-c", "--connect", dest="connect", help="If \"true\", then we assume the app is hosting and "
                                                              "thus, we must connect to it.", default="false")

    (options, args) = parser.parse_args()

    # parse CLI options given
    if not options.zmq_bind_address:
        parser.error("ZMQ address not given")
    zmq_addr, zmq_port = split_addr_port(options.zmq_bind_address)
    LOG.info("Parsed ZMQ address: %s:%d" % (zmq_addr, zmq_port))

    if not options.http_bind_address:
        parser.error("HTTP address not given")
    http_bind_addr, http_bind_port = split_addr_port(options.http_bind_address)
    LOG.info("Parsed HTTP binding address: %s:%d" % (http_bind_addr, http_bind_port))

    if not options.destination:
        parser.error("Destination not given")
    destination = options.destination
    # double check for HTTPS
    if not destination.startswith("https"):
        LOG.warning("INSECURE PROTOCOL: Destination is NOT using HTTPS.")
    LOG.info("Destination: %s" % destination)

    # then check to see if the ZMQ application is the one binding or if we're binding
    binding = options.connect == "true"
    if binding:
        LOG.info("Configured for connecting to the given ZMQ address")
    else:
        LOG.info("Configured for receiving ZMQ connection")

    # check if we want to inject into a python app instead
    if options.inject:
        BridgeInjector.inject(options.inject, zmq_addr, zmq_port, http_bind_addr, http_bind_port, destination)
    else:
        start_bridge(zmq_addr, zmq_port, http_bind_addr, http_bind_port, destination, binding)


def start_bridge(zmq_addr, zmq_port, http_bind_addr, http_bind_port, destination, binding):
    logging.getLogger("BridgeMain").info("Starting bridge...")
    # create our bridges
    zmq_bridge = ZMQBridge.Bridge(zmq_addr, zmq_port, destination, binding)
    TwistedHttpBridge.Bridge(zmq_bridge, http_bind_addr, http_bind_port)
    # start Twisted; with txZMQ, ZeroMQ is also managed by Twisted
    reactor.run()


def split_addr_port(input_combo: str) -> (str, int):
    splitted = input_combo.split(":", 1)
    return splitted[0].strip(), int(splitted[1])


if __name__ == "__main__":
    main()
