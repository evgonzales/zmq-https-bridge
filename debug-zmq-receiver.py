# debugging zmq receiving application - does nothing but receive and print
# the "World" in "Hello, World"
import zmq
import time
import sys

context = zmq.Context()
socket = context.socket(zmq.PAIR)
socket.connect("tcp://127.0.0.1:9935")

while True:
    msg = socket.recv()
    print("[!] recv: %s" % str(msg))
    time.sleep(1)
socket.close()