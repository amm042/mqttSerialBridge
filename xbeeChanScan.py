import xbeeDevice
import time
import logging
import struct
logging.basicConfig(level=logging.DEBUG)

def rx(dev, src, data):
    
    print("RX: [{:x}, {}dBm]: {}".format(src, dev.rssi_history[-1], data))
    
    xb.send(b'PONG', dest = src)
    print("TX [{:x}]: PONG ".format(src))
    
    
    
    
xb = xbeeDevice.XBeeDevice('/dev/ttyUSB0:38400:8N1', rx)

#xbee uses the first MF chnanels from the CM mask. [MFdefault is 25]



try:
    
    #print("TX [{:x}]: PING".format(0xffff))
    #xb.send(b'PING', dest = 0xffff)
    
    #0-24
    #25-49
    #50-63
    
    mask = 0x1ffffff
    
    for i in range(3):
                
        xb.send_cmd("at", command=b'CM', parameter=struct.pack(">Q", mask & 0xffffffffffffffff))
        xb.send_cmd("at", command=b'CM') # read the new CM
        xb.send_cmd("at", command=b'ED')
                

        #xb.send_cmd("at", command=b'ND')
            
        
        time.sleep(1)
        
        mask <<= 25
        mask = (mask & 0xffffffffffffffff) | (mask >> 64)
    
finally:
    xb.close()    
    
    
    
    