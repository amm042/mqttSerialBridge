#!/usr/bin/python3
import xbeeDevice
import time
import struct
import logging
import random
import os
#logging.basicConfig(level=logging.INFO)

logfile =  os.path.splitext(sys.argv[0])[0] + ".log"

logging.basicConfig(level=logging.INFO,
                    handlers=(logging.StreamHandler(stream=sys.stdout),
                              logging.handlers.RotatingFileHandler(logfile,
                                                                    maxBytes = 256*1024,
                                                                    backupCount = 6), ),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def rx(dev, src, data):
    
    logging.info("RX [{:x}, {}dBm]: {}".format(src, dev.rssi_history[-1], data))
    
    xb.send(b'PONG', dest = src)
    logging.info("TX [{:x}]: PONG ".format(src))
xb = xbeeDevice.XBeeDevice('/dev/ttyUSB0:38400:8N1', rx)

try:
    xb.send_cmd("at", command=b'PL', parameter = b'\x04')
    xb.send_cmd("at", command=b'HP', parameter = b'\x03')
    xb.send_cmd("at", command=b'ID', parameter = b'\x33\x33')
    
    # channel mask for dana roof from scanning
    xb.send_cmd("at", command=b'CM', parameter=struct.pack(">Q", 0xfceb29f032404210))
    xb.send_cmd("at", command=b'CM')
    time.sleep(0.5)
    xb.send_cmd("at", command=b'ED')
    while True:
        logging.info("TX [{:x}]: PING".format(0xffff))
        xb.send(b'PING', dest = 0xffff)
        
        
        
        time.sleep(0.5 + random.random())
        
        
        
    
finally:
    xb.close()    
    
    
    
    
