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
      

class XTPServer():
    def rx(self, xbeedev, srcaddr, fragdata):
        self.last_activity = datetime.datetime.now()        
        data = frag.receive_frag(fragdata)
        if data != None:
            logging.info("RX [{:x}<-{:x}]: COMP {} -- {}".format(self.xbee.address,
                                                            srcaddr,
                                                     data, 
                                                     hexdump.dump(data)))
        else:
            logging.info("RX [{:x}<-{:x}]: INCOMPLETE {} -- {}".format(self.xbee.address,
                                                            srcaddr,
                                                     fragdata, 
                                                     hexdump.dump(fragdata)))
        

    
    def __init__(self, portstr):
        self.xbee = XBeeDevice(portstr, self.rx, XBee)
        #self.xbee.send_cmd("at", command=b'MY', parameter=b'\x15\x15')
        
        #self.xbee.send_cmd("at", command=b'MM', parameter=b'\x02')
        #self.xbee.send_cmd("at", command=b'CH')
        #self.xbee.send_cmd("at", command=b'ID')
        
        logging.info("my address: {:x}".format(self.xbee.address))
        logging.info("MTU: {}".format(self.xbee.mtu))
        self.last_activity = datetime.datetime.now()
        self.beacon_time = datetime.timedelta(seconds=3)

    def send(self, data, dest=0xffff):
        "send with fragmentation"
        
        self.last_activity = datetime.datetime.now()
        parts = []
        for f in frag.make_frags(data, threshold=self.xbee.mtu):
            e = self.xbee.send(f, dest)
            logging.info("TX [{:x}->{:x}][{}]: {}".format(self.xbee.address,
                                                      dest,
                                                      e.fid, hexdump.dump(f)))
            parts.append(e)
                         
        for part in parts:
            if part.wait(self.xbee._timeout.total_seconds()):
                logging.info("TX [{}] complete: {}".format(part.fid, part.pkt))
            else:
                logging.info("TX [{}] timeout".format(part.fid))

    def run_forever(self):
        
        while True:
            if datetime.datetime.now() - self.last_activity > self.beacon_time:
                self.send(b'HELLO', 0xffff)
                #self.last_activity = datetime.datetime.now()
                
            time.sleep(1)
        
if __name__ == "__main__":
    # run the Server
    
    xtpsvr = None
    try:
        xtpsvr = XTPServer(sys.argv[1])
        xtpsvr.run_forever()
    finally:
        if xtpsvr != None:
            xtpsvr.xbee.close()
            
            