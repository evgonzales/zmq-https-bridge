import hashlib
import sys

import zmq


def main():
    if len(sys.argv) != 2:
        print("usage: %s <protocol://destination:port>" % sys.argv[0])
        return

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(sys.argv[1])

    while True:
        print("[.] Awaiting new messages...")

        msg = socket.recv()
        hash = hashlib.sha256(msg).hexdigest()
        print("[!] Received new message: \"%s\"" % msg.decode())

        socket.send(hash.encode())
        print("[.] Sent message: \"%s\"" % hash)


if __name__ == "__main__":
    main()
