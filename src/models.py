import struct

class Segment:
    """Transport Layer Segment"""
    def __init__(self, seq_num, data):
        self.seq_num = seq_num
        self.data = data
        self.header_size = 8 

    def pack(self):
        # 4 byte seq_num + 4 byte padding = 8 byte header
        header = struct.pack('!I4s', self.seq_num, b'\x00'*4)
        return header + self.data

class Frame:
    """Link Layer Frame (Selective Repeat)"""
    def __init__(self, seq_num, frame_type, payload):
        self.seq_num = seq_num
        self.frame_type = frame_type # 'DATA' or 'ACK'
        self.payload = payload
        self.header_size = 24

    def pack(self):
        # 4 byte seq + 1 byte type + 19 byte padding = 24 byte header
        type_code = 1 if self.frame_type == 'DATA' else 2
        header = struct.pack('!IB19s', self.seq_num, type_code, b'\x00'*19)
        return header + self.payload
