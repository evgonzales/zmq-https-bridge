import zmq
import time
import sys

context = zmq.Context()
socket = context.socket(zmq.PAIR)
socket.connect("tcp://127.0.0.1:9933")

while True:
    socket.send(str(time.time_ns() // 1000000).encode())
    print("[.] sent message")
    time.sleep(1)
socket.close()