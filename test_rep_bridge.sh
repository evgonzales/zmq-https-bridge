killall python3
python3 debug-zmq-rep.py tcp://127.0.0.1:9933 > rep_out.txt 2>&1 &
sleep 3
python3 BridgeApplication.py 127.0.0.1:9933 10.0.1.84:8080 http://10.0.1.38:8080 true
killall python3
