screen -S zmq_app -d -m python3 debug-zmq-rep.py tcp://0.0.0.0:9933
screen -S bridge -d -m python3 zmq-http-bridge.py 8181 8080 http://192.168.1.128:8080