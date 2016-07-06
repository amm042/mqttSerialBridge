import xbeeDevice
import time
import logging
#$logging.basicConfig(level=logging.DEBUG)

def rx(dev, src, data):
    
    print("RX: [{:x}, {}dBm]: {}".format(src, dev.rssi_history[-1], data))
    
    xb.send(b'PONG', dest = src)
    print("TX [{:x}]: PONG ".format(src))
xb = xbeeDevice.XBeeDevice('/dev/ttyUSB0:38400:8N1', rx)

try:
    xb.send_cmd("at", command=b'PL', parameter = b'\x00')
    xb.send_cmd("at", command=b'HP', parameter = b'\x03')
    xb.send_cmd("at", command=b'ID', parameter = b'\x33\x33')
    while True:
        print("TX [{:x}]: PING".format(0xffff))
        xb.send(b'PING', dest = 0xffff)
        time.sleep(0.5)
    
finally:
    xb.close()    
    
    
    
    