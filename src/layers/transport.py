# transport.py - Transport Layer with Buffer Management and Backpressure

from config import RECEIVER_BUFFER_SIZE, TRANSPORT_HEADER_SIZE
from models import Segment
import struct
import zlib

class TransportLayer:
    def __init__(self, segment_payload_size):
        self.L = segment_payload_size
        self.buffer_capacity = RECEIVER_BUFFER_SIZE  # 256 KB
        
        # Receiver state
        self.receive_buffer = {}  # {seq_num: data}
        self.current_buffer_usage = 0
        self.next_expected_seq = 0
        self.delivered_count = 0
        
    # === SENDER SIDE ===
    
    def segmentize(self, total_data):
        """Segment data into L-sized chunks with 8-byte header."""
        segments = []
        for i in range(0, len(total_data), self.L):
            chunk = total_data[i : i + self.L]
            seq_num = i // self.L
            segments.append(Segment(seq_num, chunk))
        return segments
    
    def compute_checksum(self, data):
        """Compute CRC32 checksum for integrity verification."""
        return zlib.crc32(data) & 0xFFFFFFFF
    
    def verify_integrity(self, data, expected_checksum):
        """Verify data integrity using checksum."""
        return self.compute_checksum(data) == expected_checksum
    
    # === RECEIVER SIDE ===
    
    def can_accept(self, data_size):
        """Check if buffer has space for incoming segment."""
        return self.current_buffer_usage + data_size <= self.buffer_capacity
    
    def get_buffer_usage_percent(self):
        """Return buffer usage as percentage."""
        return (self.current_buffer_usage / self.buffer_capacity) * 100
    
    def should_delay_ack(self):
        """Delayed ACK when buffer > 80% full."""
        return self.get_buffer_usage_percent() > 80
    
    def receive_segment(self, seq_num, data, checksum=None):
        """
        Accept segment into buffer with integrity verification.
        Returns: (success, should_ack)
        """
        data_size = len(data)
        
        # Integrity check if checksum provided
        if checksum is not None:
            if not self.verify_integrity(data, checksum):
                return False, False  # Corrupted, reject
        
        # Backpressure: reject if buffer full
        if not self.can_accept(data_size):
            return False, False
        
        # Store if not duplicate
        if seq_num not in self.receive_buffer:
            self.receive_buffer[seq_num] = data
            self.current_buffer_usage += data_size
        
        # Decide if ACK should be delayed
        should_ack = not self.should_delay_ack()
        
        return True, should_ack
    
    def app_consume(self, max_bytes):
        """
        Application layer consumes data from buffer.
        Removes in-order delivered segments.
        Returns bytes consumed.
        """
        consumed = 0
        
        while self.next_expected_seq in self.receive_buffer and consumed < max_bytes:
            data = self.receive_buffer[self.next_expected_seq]
            data_size = len(data)
            
            del self.receive_buffer[self.next_expected_seq]
            self.current_buffer_usage -= data_size
            self.delivered_count += 1
            consumed += data_size
            self.next_expected_seq += 1
        
        return consumed
    
    def get_next_expected(self):
        """Return next expected in-order sequence number."""
        return self.next_expected_seq
