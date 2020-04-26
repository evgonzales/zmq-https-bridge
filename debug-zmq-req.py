import hashlib
import random
import sys
from datetime import datetime as time

import zmq

MSG_LENGTH = 16


def main():
    if len(sys.argv) != 2:
        print("usage: %s <dest protocol://dest:port>" % sys.argv[0])
        return

    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(sys.argv[1])

    start = time.now()

    for req in range(1000):
        # generate random character sequence for testing
        msg = ''.join(
            random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(MSG_LENGTH)
        )

        hash = hashlib.sha256(msg.encode()).hexdigest()
        socket.send(msg.encode())
        print("[!] Sent new message: \"%s\" (request #%d)" % (msg, req))

        server_hash = socket.recv().decode()
        print("[.] Received digest, validating...")

        if hash == server_hash:
            print("[+] Hash test passed.")
        else:
            raise ValueError("Hash test FAILED. (got %s, expected %s)" % (server_hash, hash))

    end = time.now()
    delta = end - start
    print("[*] 1000 requests processed in %d seconds (%f requests per second)"
          % (delta.seconds, 1000 / delta.seconds))


if __name__ == "__main__":
    main()
