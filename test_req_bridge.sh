screen -S bridge -d -m python3 zmq-http-bridge.py 8181 8080 http://192.168.1.129:8080
screen -S zmq_app -d -m python3 debug-zmq-req.py tcp://127.0.0.1:8181
