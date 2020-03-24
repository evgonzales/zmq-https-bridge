import zmq
import http.server
import threading
import logging
import requests
import base64

# the address for our TCP sockets to bind to - typically loopback address
BINDING_NAME = "127.0.0.1"

# the ports to utilize for communication
ZMQ_PORT = 9933
HTTP_PORT = 9934

# the destination HTTPS server ("point B")
DESTINATION = "http://localhost:9934"

# global bridge context - don't set manually
BRIDGE_CONTEXT = None

class BridgeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(405)
        self.end_headers()
        
    def do_POST(self):
        # check for Content-Length header
        content_len_as_str = self.headers.get('Content-Length')
        
        if content_len_as_str == None:
            # didn't even get one - send back 411 to indicate requires length
            logging.warning("no Content-Length found - bad request?")
            self.send_response(411)
            self.end_headers()
            return
            
        content_len = int(content_len_as_str)
        if content_len == 0:
            # content_len_as_str wasn't a number or was 0; send back 400
            logging.warning("got bad Content-Length")
            self.send_response(400)
            self.end_headers()
            return
        
        # http.server doesn't allow for a customized constructor - need to pass it through
        # global variables, unfortunately - TODO: don't use global variables
        BRIDGE_CONTEXT.zmq_data = base64.b64decode(self.rfile.read(content_len))
        self.send_response(200)
        self.end_headers()

class BridgeContext:
    def __init__(self):
        # initialize an HTTP server and use our BridgeRequestHandler to process
        self.http_server = http.server.HTTPServer((BINDING_NAME, HTTP_PORT), BridgeRequestHandler)
        logging.info("HTTP server, binded to %s:%d" % (BINDING_NAME, HTTP_PORT))
        
        # setup ZMQ context
        self.zmq_context = zmq.Context()
        # then setup a ZSocket in PAIR mode, so we don't have to follow the send-recv-repeat pattern
        self.zmq_socket = self.zmq_context.socket(zmq.PAIR)
        # bind to loopback (or whatever we need to bind to; should be 127.0.0.1 to prevent leakage)
        self.zmq_socket.bind("tcp://%s:%d" % (BINDING_NAME, ZMQ_PORT))
        logging.info("ZMQ recv socket, binded to %s:%d" % (BINDING_NAME, ZMQ_PORT))
        
        self.running = True
    
    def tick_zmq_socket(self):
        # core function for the ZMQ listening thread
        logging.info("beginning ZMQ socket ticking")
        while self.is_running():
            recv_zmq_data = self.zmq_socket.recv()
            logging.info("received new message - forwarding")
            
            # encode data into b64, prevents possibly bad HTTP server from interpreting as ASCII rather than bytes
            encoded = base64.b64encode(recv_zmq_data)
            # fire off our request
            # SEMI-BUG: requests.post() takes a bit for some weird reason - seems to be an issue everywhere
            # since we might move to twisted, we can replace this later
            requests.post(DESTINATION, data=encoded)
            
            logging.info("forwraded %d bytes to http server" % len(encoded))
    
    def tick_http_server(self):
        # core function for the HTTP listening thread
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
        
        # got CLI settings; parse them
        # and re-set the global values, kinda bad? should move to constructor-based
        global ZMQ_PORT
        global HTTP_PORT
        global DESTINATION
        ZMQ_PORT = int(sys.argv[1])
        HTTP_PORT = int(sys.argv[2])
        DESTINATION = sys.argv[3]
        logging.info("using cli settings: ZMQ_PORT=%d, HTTP_PORT=%d, DESTINATION=%s" % (ZMQ_PORT, HTTP_PORT, DESTINATION))
    
    # set our global bridge context - should also be constructor based
    global BRIDGE_CONTEXT
    BRIDGE_CONTEXT = BridgeContext()
    
    # spin two threads up, one for HTTP and one for ZMQ, to prevent one from blocking the other
    # if possible, move to coroutines or something with async to operate on only one thread
    http_thread = threading.Thread(target=BRIDGE_CONTEXT.tick_http_server, args=())
    zmq_thread = threading.Thread(target=BRIDGE_CONTEXT.tick_zmq_socket, args=())
    
    # fire threads up
    http_thread.start()
    zmq_thread.start()

    # then wait for either to die
    while http_thread.is_alive() and zmq_thread.is_alive():
        http_thread.join(1)
        zmq_thread.join(1)

def setup_logging_levels():
    # use symbols to indicate level, rather than words - a bit easier to read
    logging.addLevelName(logging.CRITICAL, "!")
    logging.addLevelName(logging.ERROR, "-")
    logging.addLevelName(logging.WARNING, "?")
    logging.addLevelName(logging.INFO, ".")
    logging.addLevelName(logging.DEBUG, "~")
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
    
if __name__ == "__main__":
    main()