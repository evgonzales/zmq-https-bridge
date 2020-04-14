import zmq
import hashlib

def main():
    if len(sys.argv) != 2:
        print("usage: %s <protocol://destination:port>" % sys.argv[0])
        return
    
    sha = hashlib.sha256()
    
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(sys.argv[1])
    
    while True:
        msg = socket.recv()
        hash = hashlib.sha256(msg).hexdigest()
        print("[!] Received new message: \"%s\"" % msg)
        
        socket.send(hash.encode())
        print("[.] Sent message: \"%s\"" % msg)
        
        # wait so we don't flood
        time.sleep(5)
    
if __name__ == "__main__":
    main()