from xbeeDevice import XBeeDevice 
import logging
import threading
import queue
import gzip

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
        
        data = gzip.decompress(data)
         
        self.LOG.debug("rx [{}] bytes from {:x}: {}".format(len(data),
                                                            source,                                                    
                                                            data))
        self.link.proxy(data)
    
    def write(self, data):
        ilen = len(data)
        data = gzip.compress(data)
        ratio = len(data)/float(ilen)
        if self._remote_addr!= None:
            self.LOG.debug("tx [{}, cr={}] bytes to {:x}: {}".format(len(data),ratio,
                                                                self._remote_addr,                                                    
                                                                data))
            self.xbee.sendwait(data, dest=self._remote_addr)
            
        else:
            self.LOG.debug("tx [{}, cr={}] bytes WITHOUT REMOTE: {}".format(len(data),ratio,                                                                                                        
                                                    data))
                        
                        