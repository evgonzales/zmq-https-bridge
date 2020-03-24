# debugging HTTP server - purely meant to print out received encoded+decoded b64 data
# does nothing else otherwise

import http.server
import logging
import sys
import os
import base64

class DebugHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        content_len_as_str = self.headers.get('Content-Length')
        if content_len_as_str == None:
            self.send_response(411)
            self.end_headers()
            return
            
        content_len = int(content_len_as_str)
        if content_len == 0:
            self.send_response(400)
            self.end_headers()
            return
            
        zmq_data = self.rfile.read(content_len)
        logging.info("received %d bytes:" % (content_len))
        logging.info("\tencoded: %s" % (zmq_data))
        logging.info("\tdecoded: %s" % (base64.b64decode(zmq_data)))
        
        self.send_response(200)
        self.end_headers()

def main():
    setup_logging_levels()
    http_server = http.server.HTTPServer(("localhost", 9936), DebugHTTPHandler)
    logging.info("begin listening for requests")
    http_server.serve_forever()

def setup_logging_levels():
    logging.addLevelName(logging.CRITICAL, "!")
    logging.addLevelName(logging.ERROR, "-")
    logging.addLevelName(logging.WARNING, "?")
    logging.addLevelName(logging.INFO, ".")
    logging.addLevelName(logging.DEBUG, "~")
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
        
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Got keyboard interrupt - dying")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)