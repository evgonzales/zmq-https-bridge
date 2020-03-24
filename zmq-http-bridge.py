import zmq
import http.server
import threading
import logging
import requests
import base64

from handlers import BridgeRequestHandler

BINDING_NAME = "127.0.0.1"

ZMQ_PORT = 9933
HTTP_PORT = 9934

DESTINATION = "http://localhost:9934"

BRIDGE_CONTEXT = None
        

class BridgeContext:
    def __init__(self):
        self.http_server = http.server.HTTPServer((BINDING_NAME, HTTP_PORT), BridgeRequestHandler)
        logging.info("HTTP server, binded to %s:%d" % (BINDING_NAME, HTTP_PORT))
        
        self.zmq_context = zmq.Context()
        
        self.zmq_socket = self.zmq_context.socket(zmq.PAIR)
        self.zmq_socket.bind("tcp://%s:%d" % (BINDING_NAME, ZMQ_PORT))
        logging.info("ZMQ recv socket, binded to %s:%d" % (BINDING_NAME, ZMQ_PORT))
        
        self.running = True
    
    def tick_zmq_socket(self):
        logging.info("beginning ZMQ socket ticking")
        while self.is_running():
            zmq_data = self.zmq_socket.recv()
            logging.info("received new message - forwarding")
            
            encoded = base64.b64encode(zmq_data)
            requests.post(DESTINATION, data=encoded)
            
            logging.info("forwraded %d bytes to http server" % len(encoded))
    
    def tick_http_server(self):
        logging.info("beginning HTTP server ticking")
        while self.is_running():
            self.http_server.handle_request()
            logging.info("received http request - processed")
            self.zmq_socket.send(self.zmq_data)
            logging.info("forwarded %d bytes to zmq app " % len(self.zmq_data))
            
    def get_zmq_socket(self):
        return self.zmq_socket
        
    def get_http_server(self):
        return self.http_server
        
    def is_running(self):
        return self.running
        
    def set_running(self, state):
        self.running = state

def main():
    setup_logging_levels()
    
    if len(sys.argv) >= 4:
        global ZMQ_PORT
        global HTTP_PORT
        global DESTINATION
        ZMQ_PORT = int(sys.argv[1])
        HTTP_PORT = int(sys.argv[2])
        DESTINATION = sys.argv[3]
        logging.info("using cli settings: ZMQ_PORT=%d, HTTP_PORT=%d, DESTINATION=%s" % (ZMQ_PORT, HTTP_PORT, DESTINATION))
    
    global BRIDGE_CONTEXT
    BRIDGE_CONTEXT = BridgeContext()
    
    http_thread = threading.Thread(target=BRIDGE_CONTEXT.tick_http_server, args=())
    zmq_thread = threading.Thread(target=BRIDGE_CONTEXT.tick_zmq_socket, args=())
    
    http_thread.start()
    zmq_thread.start()

    while http_thread.is_alive() and zmq_thread.is_alive():
        http_thread.join(1)
        zmq_thread.join(1)
    
def setup_logging_levels():
    logging.addLevelName(logging.CRITICAL, "!")
    logging.addLevelName(logging.ERROR, "-")
    logging.addLevelName(logging.WARNING, "?")
    logging.addLevelName(logging.INFO, ".")
    logging.addLevelName(logging.DEBUG, "~")
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
    
if __name__ == "__main__":
    main()