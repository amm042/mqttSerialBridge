class xTP:
    # message ids
    HELLO = b'\x08'
    SEND32_REQ = b'\x09'   # send file with 32 bit fragments
    SEND32_BEGIN = b'\x0a' # ack send file
    SEND32_GETACKS = b'\x0b'
    SEND32_ACKS = b'\x0c'
    SEND32_DATA = b'\x0d'
    SEND32_DONE = b'\x0e'