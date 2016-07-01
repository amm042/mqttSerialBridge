import sProxy
import logging

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    
    px = sProxy.SProxy('xbee:/dev/ttyUSB0:38400:8N1:True',
                       'tcpclient:amm042:1883')
    px.run(timeout=None)
    