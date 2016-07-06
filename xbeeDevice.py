#from xbee import XBee

import threading
import serial
import time
import logging
import struct
import datetime
from xb900hp import XBee900HP
import traceback

class XBeeDied(Exception): pass

class XBeeDevice:
    MAX_TIMEOUTS = 6
    
    def __init__(self, portstr, rxcallback):
        
        self._portstr = portstr
        
        self.log = logging.getLogger(__name__)
        self.rssi_history = 10*[0]
        
        self._rxcallback = rxcallback
        self._next_frame_id = 1    
        self._max_packets = 3
        self._timeout = datetime.timedelta(seconds=5)        

        self.address = 0        
        self.on_energy = None
        
        self._mkxbee()
        
        
        
    def _mkxbee(self):
        
        self._pending = {}  
        
        self._lock = threading.Lock()
        
        self._timeout_err_cnt = 0
        self._idle = threading.Event()
        
        
        self._channel_mask = 0
        self._channel_cache= {}
        
        self.log.debug("Opening serial: " + self._portstr)
        dev, baud, opts = self._portstr.split(":")
        self._serial = serial.Serial(dev, baudrate=int(baud), 
                                     bytesize=int(opts[0]),
                                     parity=opts[1],
                                     stopbits=int(opts[2]))
        self._xbee = XBee900HP(self._serial, escaped=True,
                          callback=self._on_rx,
                          error_callback = self._on_error)

        # point to multipoint
        self.send_cmd("at", command=b'TO', parameter=b'\x40')
        self.send_cmd("at", command=b'CM')
        self.send_cmd("at", command=b'SL')
        self.send_cmd("at", command=b'SH')
        self.flush()
        
    def flush(self):
        if not self._idle.wait(self._timeout.total_seconds()):
            
            try:
                self._lock.acquire()
                self._timeout_err_cnt += 1
                
                # drop anything we migth be waiting for
                self._pending = {}
                self._idle.set()
                
                if self._timeout_err_cnt > XBeeDevice.MAX_TIMEOUTS:
                    raise XBeeDied("flush with too many timeouts")
                raise TimeoutError("Flush timeout.")
            finally:
                self._lock.release()
        self._timeout_err_cnt = 0
        
    def sendwait(self, data, timeout = None, **kwargs):
        'send the message and wait for the result'
        
        # may raise timeouterror     
        self.flush()
                              
        e = self.send(data, **kwargs)
        if timeout == None:
            timeout = self._timeout.total_seconds()
        if not e.wait(timeout):
            try:
                self._lock.acquire()
                self._timeout_err_cnt += 1
                if self._timeout_err_cnt > XBeeDevice.MAX_TIMEOUTS:
                    raise XBeeDied("sendwait too many timeouts")
                
                if e.fid in self._pending:
                    del self._pending[e.fid]
                else:
                    self.log.error("sendwait timeout, but no matching frame id {}".format(e.fid))
                    
                raise TimeoutError("Timeout sending message")
            finally:
                self._lock.release()                
        self._timeout_err_cnt = 0
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
        
        try:
            self._lock.acquire()
            self._pending[fid] = e
        finally:
            self._lock.release()
            
        e.fid = fid
        
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
        self.log.warn(traceback.format_exc())
        self._serial.close()
        self._xbee = None
        self._serial = None
        
        self._mkxbee()        
    
    def freq_to_maskbit(self, freq):
        atfreq = 902.4
        max = 920.8
        step = 0.4        
        i = 1
        
        while abs(atfreq - freq) > 0.01 and atfreq < max:
             atfreq += step
             i <<= 1
             
        return i
        
    def channel_to_freq(self, i):
                
        if i in self._channel_cache:
            return self._channel_cache[i]
        
        # return the ith enabled bit in the channel mask
        freq = 902.4
        step = 0.4
        cm = self._channel_mask
        cnt = 0
                
        # find first freq
        while cm & 0x1 == 0x0:            
            freq+=step
            cm >>= 1

        self._channel_cache[cnt] = freq
        
        while i > 0:
            cnt += 1            
            i-=1
            freq+=step
            cm >>= 1
            # check if new channel is disabled
            while cm & 0x1 == 0x0:                
                freq+=step
                cm >>= 1
            self._channel_cache[cnt] = freq
        
        return freq
        
    def _on_rx(self, pkt):
        self.log.debug("xbee rx [{:x}, {}]: {}".format(self.address, pkt['id'], pkt))            
        
        try:
            self._lock.acquire()
            
            if 'frame_id' in pkt and pkt['frame_id'] in self._pending:
                self._pending[pkt['frame_id']].pkt = pkt
                self._pending[pkt['frame_id']].set()
                del self._pending[pkt['frame_id']]
            
            if len(self._pending) == 0:
                self._idle.set()                
        finally:
            self._lock.release()
                        
        if pkt['id'] == 'tx_status':
            if pkt['status'] != b'\x00':
                s = pkt['status']
                if s in XBee900HP.tx_status_strings:
                    self.log.warn("unsuccessful tx: {}".format(XBee900HP.tx_status_strings[s]))
                else:
                    self.log.warn("unsuccessful tx: {}".format(s))
                    
        if pkt['id'] == 'at_response':                                               
            if pkt['command'] == b'SL':
                self.address = (0xffffffff00000000 & self.address) | (struct.unpack('>L', pkt['parameter'])[0]) 
            elif pkt['command'] == b'SH':
                self.address = (0x00000000ffffffff & self.address) | (struct.unpack('>L', pkt['parameter'])[0] << 32)
            elif pkt['command'] == b'DB':
                self.log.info("RSSI -{}dBm".format(pkt['parameter'][0] ))
                
                self.rssi_history.pop()
                self.rssi_history.append(-pkt['parameter'][0])
            elif pkt['command'] == b'FN':
                self.log.info("Neighbor info: {}".format(pkt['rf_data'].decode('utf-8')))
            elif pkt['command'] == b'ND':
                self.log.info("Network info: {}".format(pkt['rf_data'].decode('utf-8')))
            elif pkt['command'] == b'CM':
                # mask is sent as a hex string of varying length....
                if 'parameter' in pkt:
                    self._channel_cache ={}
                    self._channel_mask = int("".join(["{:02x}".format(i) for i in pkt['parameter']]),16)
                    self.log.info("Channel mask is {:x}".format(self._channel_mask))
            elif pkt['command'] == b'ED':
                
                for i,d in enumerate(pkt['parameter']):
                    self.log.info("Energy info [{:02d} = {:3.2f} MHz]: -{}dBm".format(i, self.channel_to_freq(i), d))
                    
                if self.on_energy != None:
                    self.on_energy (self, [(self.channel_to_freq(i), d) for i,d in enumerate(pkt['parameter'])])
            else:
                self.log.warn("Unsupported command response: {}:{}".format(pkt['command'], pkt))
        if pkt['id'] == 'rx':
            # poll rssi
            self.send_cmd("at", command=b'DB')
                        
            self._rxcallback(self, 
                             struct.unpack(">Q", pkt['source_addr'])[0], 
                             pkt['rf_data'])                

        
    def close(self):
        self._xbee.halt()
        self._serial.close()
        
        