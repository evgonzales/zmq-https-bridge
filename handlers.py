# bridge request handler - need to move around eventually

import http.server

class BridgeRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(405)
        self.end_headers()
        
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
            
        self.server.zmq_data = base64.b64decode(self.rfile.read(content_len))
        self.send_response(200)
        self.end_headers()