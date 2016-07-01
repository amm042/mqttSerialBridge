#from xbee import XBee

import threading
import serial
import time
import logging
import struct
import datetime
from xb900hp import XBee900HP

class XBeeDevice:
        
    def __init__(self, portstr, rxcallback):
        dev, baud, opts = portstr.split(":")
        self.log = logging.getLogger(__name__)
        
        self.log.debug("Opening serial: " + portstr)
        self._serial = serial.Serial(dev, baudrate=int(baud), 
                                     bytesize=int(opts[0]),
                                     parity=opts[1],
                                     stopbits=int(opts[2]))
        self._xbee = XBee900HP(self._serial, escaped=True,
                          callback=self._on_rx,
                          error_callback = self._on_error)
        self._rxcallback = rxcallback
        self._next_frame_id = 1    
        self._max_packets = 3
        self._timeout = datetime.timedelta(seconds=5)        
        self._pending = {}
        self._idle = threading.Event()
        self.address = 0
        self.send_cmd("at", command=b'TO', parameter=b'\x40')
        self.send_cmd("at", command=b'SL')
        self.send_cmd("at", command=b'SH')
        self.flush()
        
    def flush(self):
        if not self._idle.wait(self._timeout.total_seconds()):
            raise TimeoutError("Flush timeout.")
        
    def sendwait(self, data, timeout = None, **kwargs):
        'send the message and wait for the result'
        e = self.send(data, **kwargs)
        if timeout == None:
            timeout = self._timeout.total_seconds()
        if not e.wait(timeout):
            raise TimeoutError("Timeout sending message")
        return e.pkt
        
    def send(self, data, dest= 0xffff):
        'format and send a data packet, default to broadcast'
        return self.send_cmd('tx', dest_addr=struct.pack(">Q", dest), data=data)
        
    def send_cmd(self, cmd, **kwargs):
        begin = datetime.datetime.now()
        while len(self._pending) > self._max_packets:            
            if datetime.datetime.now() - begin > self._timeout:
                raise TimeoutError("Tx overrun -- are packets going out?")            
            time.sleep(0.05) 
        
        self._idle.clear()           
        e = threading.Event()
        fid = struct.pack("B", self._next_frame_id)
        self._pending[fid] = e
        
        pkt=dict(kwargs)
        pkt['id'] = cmd
        #print(pkt)
        self.log.debug("xbee tx [{:x}, pid={}, fid={}]: {}".format(self.address, 
                                                                   pkt['id'], fid, pkt))
        
        self._xbee.send(cmd, frame_id = fid, **kwargs)        
        
        self._next_frame_id += 1
        if self._next_frame_id > 0xff:
            self._next_frame_id = 1
        
        return e
        
    def _on_error(self, error):
        self.log.warn('Failed with: {}'.format(str(error)))
    def _on_rx(self, pkt):
        self.log.debug("xbee rx [{:x}, {}]: {}".format(self.address, pkt['id'], pkt))            

        if 'frame_id' in pkt and pkt['frame_id'] in self._pending:
            self._pending[pkt['frame_id']].pkt = pkt
            self._pending[pkt['frame_id']].set()
            del self._pending[pkt['frame_id']]
            
        if pkt['id'] == 'tx_status':
            if pkt['status'] != b'\x00':
                s = pkt['status']
                if s in XBee900HP.tx_status_strings:
                    self.log.warn("unsuccessful tx: {}", XBee900HP.tx_status_strings[s])
                else:
                    self.log.warn("unsuccessful tx: {}".format(s))
                    
        if pkt['id'] == 'at_response':                                               
            if pkt['command'] == b'SL':
                self.address = (0xffffffff00000000 & self.address) | (struct.unpack('>L', pkt['parameter'])[0]) 
            elif pkt['command'] == b'SH':
                self.address = (0x00000000ffffffff & self.address) | (struct.unpack('>L', pkt['parameter'])[0] << 32)
        if pkt['id'] == 'rx':
            self._rxcallback(self, 
                             struct.unpack(">Q", pkt['source_addr'])[0], 
                             pkt['rf_data'])
        
        if len(self._pending) == 0:
            self._idle.set()
        
    def close(self):
        self._xbee.halt()
        self._serial.close()