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
import shutil
from bitarray import bitarray
import argparse
import tempfile

from xTP import xTP, md5file
from xbee.ieee import XBee as XBeeS1
from xb900hp import XBee900HP

from StatsLogger import StatsBeginXfr, StatsUpdate

class XTPServer():
    def rx(self, xbeedev, srcaddr, fragdata):
        self.last_activity = datetime.datetime.now()

        logging.debug("RX [{:x}<-{:x}]: {} -- {}".format(self.xbee.address,
                                                 srcaddr,
                                                 fragdata,
                                                 hexdump.dump(fragdata)))

        if fragdata[0:1] == xTP.SEND32_REQ:
            offset, total_size, tot, crc = struct.unpack(">LLLL", fragdata[1:17])
            fname = fragdata[17:].decode('utf-8') + '.part'
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

            outpath = os.path.abspath(os.path.join(self.path,
                                                   os.path.dirname(fname)))
            os.makedirs(outpath, exist_ok=True)

            t['oid'] = StatsBeginXfr(t)
            logging.info("Begin transfer {} of {}: {}".format(t['offset'], t['total_size'],
                                                              t['filename']))
            self.txq.put((srcaddr, xTP.SEND32_BEGIN))
        elif fragdata[0:1] == xTP.MD5_CHECK and srcaddr in self.transfers:
            remotehash = fragdata[1:17]
            localhash = fragdata[17:33]
            true_filename = fragdata[33:].decode('utf-8')
            true_filename = os.path.abspath(os.path.join(self.path, true_filename))
            filename = fragdata[33:].decode('utf-8') + '.part'
            filename = os.path.abspath(os.path.join(self.path, filename))

            if os.path.exists(filename):
                d = md5file(filename)
                if d == remotehash:
                    StatsUpdate(self.transfers[srcaddr],
                                xTP.MD5_CHECK,
                                "Hash pass",
                                True)
                    logging.info("MD5 check requested on: {} -- hash check is good".format(filename))
                    shutil.move(filename, true_filename)
                else:
                    StatsUpdate(self.transfers[srcaddr],
                                xTP.MD5_CHECK,
                                "Hash fail",
                                False)
                    logging.warn("MD5 check requested on: {} -- hash ERROR -- removing file".format(filename))
                    os.remove(filename)
            else:
                StatsUpdate(self.transfers[srcaddr],
                            xTP.MD5_CHECK,
                            "Hash File Missing",
                            False)
                logging.warn("MD5 check requested on: {} -- file does not exist!".format(filename))
                d = 16 * b'\x00'
            self.txq.put( (srcaddr, xTP.MD5_CHECK + remotehash + d + fragdata[33:]))
        elif fragdata[0:1] == xTP.SEND32_GETACKS and srcaddr in self.transfers:
            logging.debug("Sending ack data. [{}]: {}".format(
                            self.transfers[srcaddr]['total_frags'],
                            self.transfers[srcaddr]['frag_mask']))
            self.transfers[srcaddr]['status'] = fragdata[0]
            self.txq.put((srcaddr, xTP.SEND32_ACKS +
                            struct.pack(">L", self.transfers[srcaddr]['total_frags']) +
                            self.transfers[srcaddr]['frag_mask'].tobytes()
                          ))

            trslt = {
                'success':sum(self.transfers[srcaddr]['frag_mask']),
                'total': len(self.transfers[srcaddr]['frag_mask']),
                }
            trslt['lost'] = trslt['total'] - trslt['success']
            StatsUpdate(self.transfers[srcaddr],
                        xTP.SEND32_GETACKS,
                        "Sending acks {} of {} received".format(
                            trslt['success'],
                            trslt['total']),
                        trslt)
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

                    StatsUpdate(self.transfers[srcaddr],
                                xTP.SEND32_DONE,
                                "Crc pass, recieved all frags",
                                True)
                    outfile = os.path.abspath(os.path.join(self.path, self.transfers[srcaddr]['filename']))

                    logging.info("File transfer complete, SUCCESS, write to {}".format(outfile))

                    #outfile.seek(self.transfers[srcaddr]['offset'], io.SEEK_SET)

                    if os.path.exists(outfile):
                        with open (outfile, 'r+b') as f:
                            f.seek(self.transfers[srcaddr]['offset'], io.SEEK_SET)
                            f.write(r)
                            f.close()
                    else:
                        # make sure output directory exists, cron job might have cleared it if empty.
                        outpath = os.path.split(outfile)[0]
                        os.makedirs(outpath, exist_ok=True)

                        with open (outfile, 'wb') as f:
                            f.seek(self.transfers[srcaddr]['offset'], io.SEEK_SET)
                            f.write(r)
                            f.close()

                else:
                    StatsUpdate(self.transfers[srcaddr],
                                xTP.SEND32_DONE,
                                "Crc Failed, recieved all frags",
                                False)
                    logging.warn("File transfer complete, CRC failure local={:x} remote={:x}".format(
                        mycrc,
                        self.transfers[srcaddr]['crc']))
            else:
                self.transfers[srcaddr]['status'] = fragdata[0]
        else:
            logging.warn("RX -- unknown message format")


    def __init__(self, portstr, filepath, xbeeclass, **kwargs):
        self.xbee = XBeeDevice(portstr, self.rx, xbeeclass, **kwargs)
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
    p = argparse.ArgumentParser()

    p.add_argument("portstr", help="pylink style port string eg: /dev/ttyUSB0:38400:8N1")
    p.add_argument("store", help="path to storage root eg: ./store")
    p.add_argument("-d", "--debug", help="logging debug level",
                    choices=['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'], default = 'INFO')
    p.add_argument("-x", "--xbee", help="XBee variant",
                    choices=['S1', '900HP'], default='S1')
    p.add_argument("-m", "--cm", help="XBee Channel Mask [Hex] (900hp)", default =None)
    xcls = {'S1': XBeeS1, '900HP': XBee900HP}

    args = p.parse_args()
    logfile = os.path.splitext(os.path.basename(sys.argv[0]))[0] + ".log"
    logging.basicConfig(level=logging.getLevelName(args.debug),
                        handlers=(logging.StreamHandler(sys.stdout),
                                  logging.handlers.RotatingFileHandler(logfile,
                                                                        maxBytes = 256*1024,
                                                                        backupCount = 2), ),
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    xtpsvr = None
    try:
        xtpsvr = XTPServer(args.portstr, args.store, xcls[args.xbee], xbeeCM= int(args.cm,16))

        xtpsvr.xbee.send_cmd("at", command=b'HP', parameter=b'\x03')
        xtpsvr.xbee.send_cmd("at", command=b'PL', parameter=b'\x04')
        xtpsvr.run_forever()
    finally:
        if xtpsvr != None:
            xtpsvr.xbee.close()
