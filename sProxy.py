

import threading
import logging
import serial
import socketserver
import time
import select
import socket
import traceback
from socketserver import ThreadingTCPServer
from xbeeServer import LinkedXbeeServer

class TCPServerHandler(socketserver.BaseRequestHandler):
    def handle(self):
        ''' handle a complete tcp connection until closed by remote
            the server is threaded, so this is blocking in its own thread
        '''       
        LOG = logging.getLogger(__name__)
        
        # add this connection to the list of clinets on the server
        self.server.clients.append(self)
        try:
            while True: 
                data = self.request.recv(1024)
                if len(data) == 0:
                    LOG.debug("client at {} disconnect".format(self.client_address[0]))
                    break
                
                LOG.debug("got [{}] bytes from {}: {}".format(len(data),
                                                                    self.client_address[0],                                                    
                                                                    data))
                
                
                # send it out
                self.server.link.proxy(data)
                
        finally:
            self.server.clients.remove(self)
            
            
class LinkedThreadingTCPServer(socketserver.ThreadingTCPServer):
    def __init__(self, server_address, RequestHandlerClass, link, bind_and_activate=True):
        socketserver.ThreadingTCPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate)
        # store the link object for callback    
        self.link = link
        self.LOG = logging.getLogger(__name__)
        self.clients = []
        
    def write(self, data):
        if len(self.clients) == 0:
            self.LOG.warn("tx [{}] bytes FAILS WITHOUT CLIENT: {}".format(len(data),                                                                                                    
                                                    data))
        else:
            for c in self.clients:
                self.LOG.debug("tx [{}] bytes to {}: {}".format(len(data),
                                                            c.client_address[0],                                                    
                                                            data))
                # todo, wrap this in try-catch and remove dead clients...
                c.request.send(data)
class ProxyTCPClient():
    def __init__(self, server_address, link):
        self.LOG = logging.getLogger(__name__)
                
        self.__is_shut_down = threading.Event()
        self.__shutdown_request = False
        self.server_address = server_address
        self.link = link
        
        self.LOG.info("TCPClient Link to {}".format(server_address))
        self.socket = None                
        
    def serve_forever(self, poll_interval=0.5):
        """Handle one request at a time until shutdown.

        Polls for shutdown every poll_interval seconds. Ignores
        self.timeout. If you need to do periodic tasks, do them in
        another thread.
        """
        self.__is_shut_down.clear()
        try:
            while not self.__shutdown_request:
                if self.socket == None:
                    time.sleep (poll_interval)
                else:
                    r, w, e = socketserver._eintr_retry(select.select, [self], [], [],
                                           poll_interval)
                    if self in r:
                        self._handle_request_noblock()
            
        finally:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
            
            self.__shutdown_request = False
            self.__is_shut_down.set()
    def shutdown(self):
        """Stops the serve_forever loop.

        Blocks until the loop has finished. This must be called while
        serve_forever() is running in another thread, or it will
        deadlock.
        """
        self.__shutdown_request = True
        self.__is_shut_down.wait()        
    def fileno(self):
        if self.socket == None:
            return None
        else:
            return self.socket.fileno()
    def _handle_request_noblock(self):
        'this is called from the main input loop when there is data to be read from the port'
        try:
            data = self.socket.recv(1024)
        except ConnectionResetError:
            data = ""            
                    
        if len(data) == 0:
            self.LOG.info("Server {} closed connection.".format(self.server_address))
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass # happens if the socket is already closed and we didn't realize
            self.socket.close()
            self.socket = None
            return
            
        self.LOG.debug("rx [{}] bytes from {}: {}".format(len(data),
                                                            self.server_address,                                                    
                                                            data))
        self.link.proxy(data)
    
    def write(self, data):
        if self.socket == None:
            self.LOG.info("Connecting to {}.".format(self.server_address))
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect(self.server_address)
            
        self.LOG.debug("tx [{}] bytes to {}: {}".format(len(data),
                                                            self.server_address,                                                    
                                                            data))
        
        try:
            b = self.socket.send(data)
        except:        
            self.socket = None
            return self.write(data)
            
        if b != len(data):
            raise Exception("length didn't match, got {} wanted {}".format(b, len(data)))
                      
class LinkedProxySerialServer():
    'like socketserver.BaseServer but for serial links'
    def __init__(self, server_address, link):            
        port, baudrate, bytesize, parity, stopbits = server_address
        # use a short timeout because this is called from a select loop
        # the value 800/ baudrate sets the timeout to the time to receive 100 bytes
        self.serial = serial.Serial(port, baudrate,bytesize, parity, stopbits, 
                                    timeout = min(0.1, 800.0 / baudrate))
        self.link = link        
        
        self.__is_shut_down = threading.Event()
        self.__shutdown_request = False
        
        self.LOG = logging.getLogger(__name__)
        self.LOG.debug("created.")    
    
    def serve_forever(self, poll_interval=0.5):
        """Handle one request at a time until shutdown.

        Polls for shutdown every poll_interval seconds. Ignores
        self.timeout. If you need to do periodic tasks, do them in
        another thread.
        """
        self.__is_shut_down.clear()
        try:
            while not self.__shutdown_request:
                r, w, e = socketserver._eintr_retry(select.select, [self], [], [],
                                       poll_interval)
                if self in r:
                    self._handle_request_noblock()
        finally:
            self.__shutdown_request = False
            self.__is_shut_down.set()
    def shutdown(self):
        """Stops the serve_forever loop.

        Blocks until the loop has finished. This must be called while
        serve_forever() is running in another thread, or it will
        deadlock.
        """
        self.__shutdown_request = True
        self.__is_shut_down.wait()            
    def fileno(self):
        return self.serial.fileno()
    
    def _handle_request_noblock(self):
        'this is called from the main input loop when there is data to be read from the port'
        data = self.serial.read(4*1024)
        
        self.LOG.debug("rx [{}] bytes from {}: {}".format(len(data),
                                                            self.serial.portstr,                                                    
                                                            data))
        self.link.proxy(data)
    
    def write(self, data):
        self.LOG.debug("tx [{}] bytes to {}: {}".format(len(data),
                                                            self.serial.portstr,                                                    
                                                            data))
        self.serial.write(data)
        
class Link():    
    '''
    loosely based on pylink.link by Salem Harrache and contributors.
    '''
    def __init__(self, url):
        "url in the form tcpserver:0.0.0.0:port or /dev/ttyUSB:9600:8N1"
        args = url.split(":")
        self.remote = None
        self.LOG = logging.getLogger(__name__) 
        if args[0] == 'tcpserver':
            host = args[1]
            port = int(args[2])
            
            socketserver.allow_reuse_address = True            
            self.link = LinkedThreadingTCPServer((host,port), TCPServerHandler, self)                        
            self.link.daemon_threads = True
            
            self.LOG.info("Started LinkTCP server on {}:{}".format(host, port))
        elif args[0] == 'tcpclient':
            host = args[1]
            port = int(args[2])
                        
            self.link = ProxyTCPClient ((host,port), self)
            self.link.daemon_threads = True
            
            self.LOG.info("Started LinkTCP client on {}:{}".format(host, port))
        elif args[0] == 'serial':
            port = args[1]  
            baudrate = int(args[2])
            bytesize = int(args[3][0])
            parity = args[3][1]
            stopbits = int(args[3][2])                   
        
            self.link = LinkedProxySerialServer( (port, baudrate, bytesize, parity, stopbits ), self)
            self.LOG.info("Started LinkSerial server on {}".format(self.link.serial.portstr))
        elif args[0] == 'xbee':
            port = args[1]
            baudrate = int(args[2])
            bytesize = int(args[3][0])
            parity = args[3][1]
            stopbits = int(args[3][2])                   
            basestation = args[4].lower() == 'true'
            
            self.link = LinkedXbeeServer( (port, baudrate, bytesize, parity, stopbits, basestation ), self)
            self.LOG.info("Started XBee server on rf address {:x}".format(self.link.address))                        
        else:
            raise NotImplementedError("url format not supported")
                        
        self.thread = threading.Thread(name='LinkServer@{}'.format(url), target=self.link.serve_forever)
        self.thread.setDaemon(True)
        self.thread.start()
    def bind (self, other):
        '''bind this link to another link, 
            data received on this link will be written to the other        
        '''
        self.remote = other
    def proxy(self, data):
        if self.remote:
            try:           
                self.remote.write(data)
            except Exception as x:
                self.LOG.critical("Remote link failed with: {}".format(x))
                self.LOG.critical(traceback.format_exc())
                self.link.shutdown()
                self.thread.join()
                self.LOG.critical("Thread stopped")
        else:
            self.LOG.error("cannot proxy data without remote.")
    
    def write(self, data):
        'write data to our link'        
        self.link.write(data)
class SProxy:    
    def __init__(self, local_url, remote_url):
        '''
        proxy data between a local and remote port.
        if xx_url is tcpserver:host:port a server is started (accepts connections)
        if xx_url is tcpclient:host:port a client connection is started (makes a connection)
        if xx_url is serial:device:baud:8N1 like strings a serial device is used            
        '''
                        
        self.LOG = logging.getLogger(__name__)  
        self.LOG.info("Creating SProxy {} <--> {}".format(local_url, remote_url))

        self.local = None
        self.remote = None
        try:
            self.local = Link(local_url)
            self.remote = Link(remote_url)
        except Exception as x:
            if self.local != None:
                self.local.link.shutdown()
            if self.remote != None:
                self.remote.link.shutdown()
                
            raise x

        # bind the links together
        self.local.bind(self.remote)
        self.remote.bind(self.local)
        self._running = True
        
    def run(self, timeout=None):
        'everything is done in the background, just sleep the main thread'
        if self._running:
            self.LOG.info("Proxy server is running.")                    
            
            if timeout != None:
                time.sleep(timeout)
            else:
                while self.local.thread.is_alive() and self.remote.thread.is_alive():
                    time.sleep(1)

        if self.local.thread.is_alive():
            self.local.link.shutdown()
            self.local.thread.join()
        if self.remote.thread.is_alive():
            self.remote.link.shutdown()
            self.remote.thread.join()

                