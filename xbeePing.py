import xbeeDevice
import time


def rx(data):
    print("RX: ", data)
    
xb = xbeeDevice.XBeeDevice('/dev/ttyUSB0:38400:8N1', rx)

try:
    while True:
        print("TX: PING")
        xb.send(b'PING', dest = 0xffff)
        time.sleep(0.5)
    
finally:
    xb.close()    