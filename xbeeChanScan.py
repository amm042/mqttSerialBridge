import xbeeDevice
import time
import logging
import struct
import numpy
logging.basicConfig(level=logging.DEBUG)

def rx(dev, src, data):
    
    print("RX: [{:x}, {}dBm]: {}".format(src, dev.rssi_history[-1], data))
    
    xb.send(b'PONG', dest = src)
    print("TX [{:x}]: PONG ".format(src))
    
    
dat = {}

def print_info():
    global dat
    global xb
    
    
    print(80*"-")
    cm = sorted(dat.items(), key=lambda x: numpy.mean(x[1]), reverse = True)
    
    for freq, dbms in cm:
         
        print ("{:03.2f} MHz = -{:3.2f} +- {:3.2f} dBm".format(freq, numpy.mean(dbms), numpy.std(dbms)))
        
    
    
    mask = 0
    for freq, dbms in cm[:25]:
        mask |= xb.freq_to_maskbit(freq)
    
    print ("Best channel mask: {:016x}: ".format(mask))
    
    print(80*"-")
                
                
                
                
def energy(dev, info):
    global dat
    for freq, dbm in info:
        #print ("{:03.2f} = {} dBm".format(freq, dbm))
        if freq in dat:
            dat[freq].append(dbm)
        else:
            dat[freq] = [dbm]
    
    print_info()
    
xb = xbeeDevice.XBeeDevice('/dev/ttyUSB0:38400:8N1', rx)
xb.on_energy = energy
#xbee uses the first MF chnanels from the CM mask. [MFdefault is 25]



try:
    
    #print("TX [{:x}]: PING".format(0xffff))
    #xb.send(b'PING', dest = 0xffff)
    
    #0-24
    #25-49
    #50-63
    
    while True:
        mask = 0x1ffffff    
        for i in range(3):
                    
            xb.send_cmd("at", command=b'CM', parameter=struct.pack(">Q", mask & 0xffffffffffffffff))
            xb.send_cmd("at", command=b'CM') # read the new CM
            xb.send_cmd("at", command=b'ED')
                        
            #xb.send_cmd("at", command=b'ND')
                            
            time.sleep(.5)
            
            mask <<= 25
            mask = (mask & 0xffffffffffffffff) | (mask >> 64)
    
finally:
    xb.close()    
    
    
    
    