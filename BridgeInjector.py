import os
import logging
import BridgeApplication
import multiprocessing
import shutil
import threading
import time

from txzmq import ZmqEndpointType

LOG = logging.getLogger("Injector")
INJECT_SOURCE = """    # ZMQ-HTTP-BRIDGE-INJECTED
    import sys
    sys.path.append("@__SCRIPT_DIRECTORY__@")
    import BridgeInjector
    BridgeInjector.inject_zeromq_bridge("@__ZMQ_ADDR__@", @__ZMQ_PORT__@, 
                                        "@__HTTP_ADDR__@", @__HTTP_PORT__@,
                                        "@__DESTINATION__@")
"""


def inject(scan_dir, zmq_addr: str, zmq_port: int, http_addr: str, http_port: int, destination: str):
    for dir, subdir, files in os.walk(scan_dir):
        LOG.info("Scanning directory %s" % dir)
        to_inject = dict()

        for file in files:
            # skip files that aren't python files
            if not file.lower().endswith(".py"):
                continue

            with open(file, "r") as file_stream:
                line = file_stream.readline()
                while line:
                    if line.startswith("if __name__ == \"__main__\":"):
                        reinject = False
                        if "# ZMQ-HTTP-BRIDGE-INJECTED" in peek_nextline(file_stream):
                            LOG.warning("File %s was already injected - reinjecting..." % file)
                            reinject = True

                        full_path = os.path.join(dir, file)
                        offset = file_stream.tell()
                        to_inject[full_path] = {offset: offset, reinject: reinject}
                        LOG.info("Found injection point at %s (offset: %d)" % (full_path, offset))
                    line = file_stream.readline()

        for target, (offset, reinject) in to_inject.items():
            if not reinject:
                shutil.copyfile(target, target + ".noninjected")
            with open(target, "r+") as file_stream:
                file_stream.seek(offset)
                if reinject:
                    # if we're reinjecting, we need to skip the current code
                    file_stream.seek(file_stream.tell() + len(INJECT_SOURCE.encode()))
                remaining = collect_remaining(file_stream)

                file_stream.seek(offset)
                file_stream.write(INJECT_SOURCE
                                  .replace("@__SCRIPT_DIRECTORY__@", os.path.dirname(os.path.realpath(__file__)))
                                  .replace("@__ZMQ_ADDR__@", zmq_addr)
                                  .replace("@__ZMQ_PORT__@", str(zmq_port))
                                  .replace("@__HTTP_ADDR__@", http_addr)
                                  .replace("@__HTTP_PORT__@", str(http_port))
                                  .replace("@__DESTINATION__@", destination)
                                  )
                for line in remaining:
                    file_stream.write(line)


def peek_nextline(file_stream) -> str:
    pos = file_stream.tell()
    line = file_stream.readline()
    file_stream.seek(pos)
    return line


def collect_remaining(file_stream) -> list:
    line = file_stream.readline()
    remaining = []
    while line:
        remaining.append(line)
        line = file_stream.readline()
    return remaining


STARTED_BRIDGE = False


def inject_zeromq_bridge(zmq_addr: str, zmq_port: int, http_bind_addr: str, http_bind_port: int, destination: str):
    from zmq import Socket as s
    from txzmq import ZmqConnection as zc

    s.__real_connect__ = s.connect
    s.__real_bind__ = s.bind

    def _start_bridge(is_app_hosting):
        global STARTED_BRIDGE
        if not STARTED_BRIDGE:
            bp = multiprocessing.Process(target=BridgeApplication.start_bridge, daemon=True,
                                         args=(zmq_addr, zmq_port, http_bind_addr, http_bind_port, destination,
                                               is_app_hosting))
            bp.start()
            # give the bridge a second to start up fully
            time.sleep(1)
            LOG.debug("Started bridge process")
            STARTED_BRIDGE = True

    # first, we need to override ZMQ's socket bind/connect to redirect it to our socket
    def _injected_bind(self, addr):
        LOG.debug("Trapped bind(%s)" % addr)
        self.__real_bind__(addr)
        _start_bridge(True)

    def _injected_connect(self, addr):
        LOG.debug("Trapped connect(%s)" % addr)
        _start_bridge(False)
        new_dst = "tcp://%s:%d" % (zmq_addr, zmq_port)
        self.__real_connect__(new_dst)
        LOG.debug("Redirected connect() call to %s" % new_dst)

    # then we need to fix txzmq's socket to use the real underlying method so we don't end up looping
    def _injected_connectOrBind(self, endpoints):
        for endpoint in endpoints:
            if endpoint.type == ZmqEndpointType.connect:
                self.socket.__real_connect__(endpoint.address)
            elif endpoint.type == ZmqEndpointType.bind:
                self.socket.__real_bind__(endpoint.address)
            else:
                assert False, "Unknown endpoint type %r" % endpoint

    s.bind = _injected_bind
    s.connect = _injected_connect
    zc._connectOrBind = _injected_connectOrBind
