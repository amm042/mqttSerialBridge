from xbeeDevice import XBeeDevice
import zlib
import fragmentation16 as frag
import logging
import sys
import os
import os.path
import logging.handlers
import hexdump
import time
import datetime
import struct
import queue
import zlib
import io
from bitarray import bitarray
from xTP import xTP

#from xbee.ieee import XBee
#from xb900hp import XBee900HP
from xb900hp import XBee900HP as XBee

logfile = os.path.splitext(sys.argv[0])[0] + ".log"

logging.basicConfig(level=logging.INFO,
                    handlers=(logging.StreamHandler(sys.stdout),
                              logging.handlers.RotatingFileHandler(logfile,
                                                                    maxBytes = 256*1024,
                                                                    backupCount = 0), ),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
      

class XTPServer():
    def rx(self, xbeedev, srcaddr, fragdata):
        self.last_activity = datetime.datetime.now()                
        
        logging.debug("RX [{:x}<-{:x}]: {} -- {}".format(self.xbee.address,
                                                 srcaddr,
                                                 fragdata, 
                                                 hexdump.dump(fragdata)))
    
        if fragdata[0:1] == xTP.SEND32_REQ:
            offset, total_size, tot, crc = struct.unpack(">LLLL", fragdata[1:17])
            fname = fragdata[17:].decode('utf-8')
            self.transfers[srcaddr] = {'filename': fname,
                                       'crc': crc,
                                       'offset': offset,
                                       'total_frags': tot,
                                       'total_size': total_size,
                                       'frag_mask': bitarray(tot),
                                       'frags': {},
                                       'status': fragdata[0]}
            t = self.transfers[srcaddr]
            t['frag_mask'].setall(0)
            
            logging.info("Begin transfer {} of {}: {}".format(t['offset'], t['total_size'],
                                                              t['filename']))
            self.txq.put((srcaddr, xTP.SEND32_BEGIN))
        elif fragdata[0:1] == xTP.SEND32_GETACKS and srcaddr in self.transfers:
            logging.debug("Sending ack data. [{}]: {}".format(
                            self.transfers[srcaddr]['total_frags'],
                            self.transfers[srcaddr]['frag_mask']))
            self.transfers[srcaddr]['status'] = fragdata[0]
            self.txq.put((srcaddr, xTP.SEND32_ACKS +
                            struct.pack(">L", self.transfers[srcaddr]['total_frags']) +
                            self.transfers[srcaddr]['frag_mask'].tobytes()
                          ))
            
        elif fragdata[0:1] == xTP.SEND32_DATA and srcaddr in self.transfers:                                                
            i = struct.unpack(">L", fragdata[1:5])[0]
            logging.debug("  got frag {}/{}".format(i, self.transfers[srcaddr]['total_frags']))
            self.transfers[srcaddr]['frags'][i] = fragdata[5:]
            self.transfers[srcaddr]['frag_mask'][i] = True
            if self.transfers[srcaddr]['frag_mask'].all() and not self.transfers[srcaddr]['status'] == xTP.SEND32_DONE:
                r = b''
                for i in range(self.transfers[srcaddr]['total_frags']):
                    r += self.transfers[srcaddr]['frags'][i]
                mycrc = zlib.crc32(r)
                self.transfers[srcaddr]['status'] = xTP.SEND32_DONE
                
                if mycrc == self.transfers[srcaddr]['crc']:
                    
                    outfile = os.path.abspath(os.path.join(self.path, self.transfers[srcaddr]['filename']))
                    logging.info("File transfer complete, SUCCESS, write to {}".format(outfile))
                    
                    if os.path.exists(outfile):                        
                        with open (outfile, 'r+b') as f:
                            f.seek(self.transfers[srcaddr]['offset'], io.SEEK_SET)
                            f.write(r)
                            f.close()
                    else:
                        with open (outfile, 'wb') as f:
                            f.seek(self.transfers[srcaddr]['offset'], io.SEEK_SET)                            
                            f.write(r)
                            f.close()   
                else:
                    logging.warn("File transfer complete, CRC failure local={:x} remote={:x}".format(
                        mycrc,
                        self.transfers[srcaddr]['crc']))
            else:
                self.transfers[srcaddr]['status'] = fragdata[0]
        else:
            logging.warn("RX -- unknown message format") 

    
    def __init__(self, portstr, filepath):
        self.xbee = XBeeDevice(portstr, self.rx, XBee)
        #self.xbee.send_cmd("at", command=b'MY', parameter=b'\x15\x15')
                
        # mode 1 = 802.15.4 NO ACKs
        self.xbee.send_cmd("at", command=b'MM', parameter=b'\x01')
        
        #self.xbee.send_cmd("at", command=b'MM', parameter=b'\x02')
        #self.xbee.send_cmd("at", command=b'CH')
        #self.xbee.send_cmd("at", command=b'ID')
        
        self.transfers = {}
        
        logging.info("my address: {:x}".format(self.xbee.address))
        logging.info("MTU: {}".format(self.xbee.mtu))
        self.last_activity = datetime.datetime.now()
        self.path = filepath
        os.makedirs(filepath, exist_ok=True)
        self.beacon_time = datetime.timedelta(seconds=3)
        self.txq = queue.Queue()

    def send(self, data, dest=0xffff):
        "send (no fragmentation)"
        
        self.last_activity = datetime.datetime.now()
        e = self.xbee.send(data, dest)
        
        logging.debug("TX [{:x}->{:x}][{}]: {}".format(self.xbee.address,
                                                  dest,
                                                  e.fid, hexdump.dump(data)))
   
        if e.wait(self.xbee._timeout.total_seconds()):
            logging.debug("TX [{}] complete: {}".format(e.fid, e.pkt))
        else:
            logging.debug("TX [{}] timeout".format(e.fid))

    def run_forever(self):
        
        while True:
            if datetime.datetime.now() - self.last_activity > self.beacon_time:                
                self.txq.put((0xffff, xTP.HELLO))                        
            try:        
                dest, msg = self.txq.get(True, self.beacon_time.total_seconds())
                self.send(dest=dest, data=msg)
                
            except queue.Empty:
                continue
                    
if __name__ == "__main__":
    # run the Server
    
    xtpsvr = None
    try:
        xtpsvr = XTPServer(sys.argv[1], sys.argv[2])
        xtpsvr.run_forever()
    finally:
        if xtpsvr != None:
            xtpsvr.xbee.close()
            
            