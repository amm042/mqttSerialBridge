import xbeeDevice
import time
import logging
logging.basicConfig(level=logging.DEBUG)

def rx(dev, src, data):
    
    print("RX: [{:x}, {}dBm]: {}".format(src, dev.rssi_history[-1], data))
    
    xb.send(b'PONG', dest = src)
    print("TX [{:x}]: PONG ".format(src))
xb = xbeeDevice.XBeeDevice('/dev/ttyUSB0:38400:8N1', rx)

try:
    
    #print("TX [{:x}]: PING".format(0xffff))
    #xb.send(b'PING', dest = 0xffff)
    xb.send_cmd("at", command=b'ED')
    #xb.send_cmd("at", command=b'ND')
        
    time.sleep(15)
    
finally:
    xb.close()    
    
    
    
    