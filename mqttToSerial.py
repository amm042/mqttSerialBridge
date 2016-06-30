import sProxy
import logging

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
      
if __name__ == "__main__":
    
    px = sProxy.SProxy('tcpserver:localhost:9999',
                       'xbee:/dev/ttyUSB0:38400:8N1:False')
    px.run(timeout=None)
    