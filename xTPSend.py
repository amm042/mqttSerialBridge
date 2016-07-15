from xbeeDevice import XBeeDevice
import zlib
import fragmentation16 as frag
import logging
import sys
import os.path
import logging.handlers
import hexdump
import time
import datetime
import threading
from xbee.ieee import XBee
#from xb900hp import XBee900HP
from scipy.stats.mstats_basic import threshold

logfile = os.path.splitext(sys.argv[0])[0] + ".log"

logging.basicConfig(level=logging.DEBUG,
                    handlers=(logging.StreamHandler(sys.stdout),
                              logging.handlers.RotatingFileHandler(logfile,
                                                                    maxBytes = 256*1024,
                                                                    backupCount = 0), ),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
      
class NoRemoteException(Exception):pass
class XTPClient():
    def rx(self, xbeedev, srcaddr, fragdata):
        self.last_activity = datetime.datetime.now()        
        data = frag.receive_frag(fragdata)
        
        if data == b'HELLO':
            self.remote = srcaddr
            self.have_remote.set()        
        elif data != None:
            logging.info("RX [{:x}<-{:x}]: {} -- {}".format(self.xbee.address,
                                                            srcaddr,
                                                     data, 
                                                     hexdump.dump(data)))
    def __init__(self, portstr):
        self.xbee = XBeeDevice(portstr, self.rx, XBee)        
        #self.xbee.send_cmd("at", command=b'MY', parameter=b'\x16\x16')
        
        logging.info("my address: {:x}".format(self.xbee.address))
        logging.info("MTU: {}".format(self.xbee.mtu))
                
        self.remote = None
        self.have_remote = threading.Event()
        
        # testing
        #self.remote = 0x1616
        #self.have_remote.set()
        
        #self.xbee.send_cmd("at", command=b'MM', parameter=b'\x02')
        #self.xbee.send_cmd("at", command=b'CH')
        #self.xbee.send_cmd("at", command=b'ID')
        
        self.last_activity = datetime.datetime.now()        
        self.beacon_time = datetime.timedelta(seconds=3)
        
        self.remote_timeout = datetime.timedelta(seconds=30)

    def send(self, data, dest=0xffff):
        "send with fragmentation, returns true on success"
        
        self.last_activity = datetime.datetime.now()
        parts = []
        for f in frag.make_frags(data, threshold=self.xbee.mtu>>1):
            e = self.xbee.send(data=f, dest=dest)
            
            logging.info("TX [{:x}->{:x}][{}]: {}".format(self.xbee.address,
                                      dest,
                                      e.fid, hexdump.dump(f)))
            parts.append(e)
            if e.wait(self.xbee._timeout.total_seconds()):
                logging.info("TX [{}] complete: {}".format(e.fid, e.pkt))
            else:
                logging.info("TX [{}] timeout".format(e.fid))
                return False
            
        return True
                         
        #for part in parts:
        #    if part.wait(self.xbee._timeout.total_seconds()):
        #        logging.info("TX [{}] complete: {}".format(part.fid, part.pkt))
        #    else:
        #        logging.info("TX [{}] timeout".format(part.fid))

    def send_file(self, filename):
        if os.path.exists(filename):
            if not self.have_remote.wait(self.remote_timeout.total_seconds()):
                raise NoRemoteException("No remote server detected.")
            with open(filename, 'rb') as f:
                data = f.read()
            self.send(data=data, dest=self.remote)
            #self.send(data=data, dest=0xffff)
        
if __name__ == "__main__":
    # run the Server
    
    xtp = None
    try:
        xtp = XTPClient(sys.argv[1])
        time.sleep(0.5)
        for filename in sys.argv[2:]:
            xtp.send_file(filename)
    finally:
        if xtp != None:
            xtp.xbee.close()
            
            