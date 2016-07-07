from xbeeDevice import XBeeDevice 
import logging
import threading
import queue
import zlib
import fragmentation as frag
import datetime

class LinkedXbeeServer():
    'like socketserver.BaseServer but for XBee API links'
    def __init__(self, server_address, link):
        
        port, baudrate, bytesize, parity, stopbits, basestation = server_address            
        self.xbee = XBeeDevice("{}:{}:{}{}{}".format(port, baudrate, bytesize, parity, stopbits),
                               self._rx)
            
        self._basestation = basestation          
        self._remote_addr = None
        
        if self._basestation == False:
            # discover the base station
            for i in range(3):
                self.xbee.sendwait(b"HELLOBASESTATION", dest=0xffff)
                    
            if self._remote_addr == None:
                raise Exception("No remote basestation could be found.")
        
        self.link = link        
        
        self._rxq = queue.Queue()
        self.__is_shut_down = threading.Event()
        self.__shutdown_request = False
        
        self._last_write = datetime.datetime.now()
                
        self.LOG = logging.getLogger(__name__)
        self.LOG.debug("created.")    
    
    def shutdown(self):
        self.__shutdown_request = True
        self.__is_shut_down.wait()    
        self.xbee.close()
        
    @property
    def address(self):
        return self.xbee.address
    def _rx(self, xbee, source, data):
        # handle magic packets to discover the base station       
        
         
        if data == b'HELLOREMOTE':
            self._remote_addr = source
        elif self._basestation and data == b'HELLOBASESTATION':
            self._remote_addr = source
            self.xbee.send(b'HELLOREMOTE', source)
        else:
            self._rxq.put( (xbee, source, data) )
    def serve_forever(self, poll_interval=0.5):
        """Handle one request at a time until shutdown.

        Polls for shutdown every poll_interval seconds. Ignores
        self.timeout. If you need to do periodic tasks, do them in
        another thread.
        """
        self.__is_shut_down.clear()
        try:
            while not self.__shutdown_request:
                try:
                    args = self._rxq.get(block = True, timeout=poll_interval)
                except queue.Empty:
                    continue
                self._handle_request_noblock(*args)
        finally:
            self.__shutdown_request = False
            self.__is_shut_down.set()
     
    
    def _handle_request_noblock(self, dest, source, data):                   
        
        #data = zlib.decompress(data)
         
        self.LOG.debug("rx [{}] bytes from {:x}: {}".format(len(data),
                                                            source,                                                    
                                                            data))
        try:
            r = frag.receive_frag(data)        
            if r != None:            
                self.link.proxy(zlib.decompress(r))
        except frag.CrcError:
            self.LOG.warn ("  couldn't decode packet, CRC error")
    def write(self, data):
        ilen = len(data)
        data = zlib.compress(data)
        ratio = len(data)/float(ilen)
        tries = 0
                
        # throttle tx so we don't break the link, wait about how long it takes to tx one packet
        now = datetime.datetime.now()            
        if now - self._last_write < self.xbee._last_sendwait_length:
            time.sleep((self.xbee._last_sendwait_length - (now - self._last_write)).total_seconds())
        self._last_write = now
                
        while self._basestation == False and self._remote_addr == None and tries < 5:
            self.xbee.sendwait(b"HELLOBASESTATION", dest=0xffff)
                    
        if self._remote_addr == None:
            self.LOG.warn("tx FAILED, NO REMOTE [{}, cr={}] bytes to {:x}: {}".format(len(data),ratio,
                                                            self._remote_addr,                                                    
                                                            data))
        else:            
            self.LOG.debug("tx [{}, cr={}] bytes to {:x}: {}".format(len(data),ratio,
                                                                self._remote_addr,                                                    
                                                                data))                                            
            
            for f in frag.make_frags(data):                
                tries = 0
                success= False
                while tries < 3 and success == False:
                    try:                            
                        p = self.xbee.sendwait(f, dest=self._remote_addr)
                        success = 'status' in p and p['status'] == b'\x00'
                    except TimeoutError as x:
                        self.LOG.warn("timeout sending message, retry ({})".format(x))
                    tries += 1
                if success == False:
                    break
                    
                        