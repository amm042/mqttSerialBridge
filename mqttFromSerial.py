import sProxy
import logging
import pidfile
import os.path
import sys
logfile = "/var/log/"+ os.path.splitext(sys.argv[0])[0] + ".log"

logging.basicConfig(level=logging.INFO,
                    handlers=(logging.handlers.RotatingFileHandler(logfile,
                                                                    maxBytes = 256*1024,
                                                                    backupCount = 6), ),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    pidfile.write()
    while True:
        px = sProxy.SProxy('xbee:/dev/ttyUSB0:38400:8N1:True',
                           'tcpclient:amm042:1883')
        px.run(timeout=None)
    