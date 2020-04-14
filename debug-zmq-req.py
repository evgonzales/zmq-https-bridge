import zmq
import hashlib
import random
import sys
import time

MSG_LENGTH = 16

def main():
    if len(sys.argv) != 2:
        print("usage: %s <protocol://destination:port>" % sys.argv[0])
        return
    
    sha = hashlib.sha256()
    
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(sys.argv[1])
    
    print("[.] Waiting 5 seconds for bridge to start...")
    time.sleep(5)
    
    while True:
        msg = ''.join(random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(MSG_LENGTH))
        hash = hashlib.sha256(msg.encode()).hexdigest()
        socket.send(msg.encode())
        print("[!] Sent new message: \"%s\"" % msg)
        
        server_hash = socket.recv().decode()
        print("[.] Received digest, validating...")
        
        if hash == server_hash:
            print("[.] Hash test passed.")
        else:
            print("[!] Hash test FAILED. (got %s, expected %s)" % (server_hash, hash))
            
if __name__ == "__main__":
    main()