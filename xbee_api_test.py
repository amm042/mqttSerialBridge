from xbeeDevice import XBeeDevice

import time
import logging


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

def rx(dest, source, data):
    log.info("{:x} -> {:x}: {}".format(source, dest.address, data))
    if data == b'PING':
        dest.send(b"HELLO", dest=source)
        
        
xb1 = None
xb2 = None
try:
    xb2 = XBeeDevice("/dev/ttyUSB1:38400:8N1", rx)    
    print('found xbee with address: {:x}'.format(xb2.address))    
    #xb1 = XBeeDevice("/dev/ttyUSB0:38400:8N1", rx)
    #print('found xbee with address: {:x}'.format(xb1.address))
    
    if 0:
            
        xb1.sendwait(b"hello", dest=xb2.address)
        xb2.sendwait(b"goodbye", dest=xb1.address)
        xb1.sendwait(b"PING", dest=0xffff)
        print("all packets sent")
        time.sleep(15)
finally:
    if xb1 != None:
        xb1.close()
    if xb2 != None:
        xb2.close()