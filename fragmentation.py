'''
quick and dirty fragmentation library.

supports up to 16 fragments. 

uses a global buffer for decoding so you can only have one message
in flight at a time, or fragments will get lost.
'''


import zlib
import math
import struct

MAGIC = b'\x15'
class CrcError(Exception): pass

def encode(frag_num, total_frags, crc, frag):        
    h = struct.pack("B", total_frags<<4 | frag_num&0xf )        
    return MAGIC + h + crc + frag
def decode(frag):
    h = frag[1]
    crc = struct.unpack(">L", frag[2:6])[0]
    return struct.pack("B", frag[0]), h>>4, h&0xf, crc, frag[6:]
def make_frags(data, threshold=121):
    '''given some data (binary string) add the fragmentation header and 
        fragment if necessary. Adds 6 bytes of overhead, so threshold of 
        121 will generate a max packet length of 127 bytes.
        returns generated fragments with appropriate headers.    
       '''   
    
    at=0
    frag_num =0
    # make total frags the 0-based frag number of the last fragment, 
    # so it is actually total_frags - 1...
    total_frags = math.floor(len(data) / float(threshold))
    crc = struct.pack(">L", zlib.crc32(data)) 
    
    if total_frags > 0xf:
        raise Exception("data too large for this format ({} is too many fragments)!".format(total_frags))
    while at<len(data):
        frag_data = data[at:at+threshold] 
        at += len(frag_data)
        yield encode(frag_num, total_frags, crc, frag_data)
        frag_num += 1
        
frag_buf = {} 
def receive_frag(frag):
    global frag_buf
    
    magic, total_frags, this_frag, crc, frag_data = decode(frag)
    if magic != MAGIC:
        return None
    frag_buf[this_frag] = (crc, frag_data)
    
    if this_frag == total_frags: 
        # attempt to reassemble
        r = b''
        for i in range(total_frags+1):
            r += frag_buf[i][1]
        mycrc = zlib.crc32(r)
        if mycrc == crc:
            return r
        else:            
            raise CrcError()
    return None

if __name__=="__main__":
    #test
    
    s=b'''Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis commodo sodales sem, sed ultrices lacus facilisis vitae. Curabitur sapien neque, aliquet vitae euismod ac, ornare egestas urna. Curabitur convallis mauris ligula, vel tempus dui porttitor quis. Sed ultricies leo turpis, vitae sagittis sem pretium aliquam. Donec eleifend id turpis ac tincidunt. Quisque leo nisi, faucibus id tincidunt id, gravida vehicula arcu. Donec volutpat rhoncus tincidunt. Proin id pharetra ex. Praesent sed urna tempor, semper felis eget, ultricies nulla. Nulla facilisi. Curabitur et augue porttitor, gravida felis a, vulputate neque. Sed et interdum risus, eget rutrum mauris. Pellentesque volutpat purus ut metus malesuada ultricies. Fusce feugiat, mauris non tempor vulputate, quam mi luctus odio, a posuere libero nisl nec felis.
Proin eget elit condimentum, hendrerit lacus quis, dignissim tellus. In congue semper finibus. Ut elementum, nibh non condimentum posuere, felis risus porttitor ligula, commodo molestie ligula elit a ligula. Sed non libero faucibus metus euismod porta ac nec ligula. Sed pharetra, velit eu pellentesque dignissim, dolor magna dapibus libero, sit amet volutpat sem tortor quis neque. Etiam ut bibendum risus. Phasellus blandit sodales sapien. Nunc sollicitudin accumsan lectus pretium lobortis. Quisque eget pretium orci. Pellentesque mauris enim, finibus vitae imperdiet non, fringilla a ex. Nam justo sapien, elementum nec risus eu, tincidunt lobortis risus. Nunc ut justo sed augue dignissim placerat. Phasellus eget ipsum rhoncus tortor tempor faucibus. Curabitur iaculis massa pellentesque, semper sapien luctus, commodo justo. Aenean a consequat quam, a vehicula risus. Proin erat tellus, pulvinar vitae dictum in, sodales quis orci.'''
    
    rslt = None
    for frag in make_frags(s):
        rslt = receive_frag(frag)
        
    assert rslt == s 
    
    s= b'test'
    rslt = None
    for frag in make_frags(s):
        rslt = receive_frag(frag)
        
    assert rslt == s 
    
    