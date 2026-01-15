# link.py - Link Layer with Selective Repeat ARQ

from config import LINK_HEADER_SIZE
from models import Frame

class LinkLayer:
    def __init__(self, window_size, timeout_interval=0.150):
        self.W = window_size
        self.timeout_interval = timeout_interval
        
        # === SENDER STATE ===
        self.send_base = 0
        self.next_seq_num = 0
        self.send_window = {}  # {seq: {'frame': Frame, 'send_time': float, 'acked': bool}}
        
        # === RECEIVER STATE ===
        self.recv_base = 0
        self.recv_buffer = {}  # {seq: payload} for out-of-order
        self.pending_acks = []  # List of ACKs to send
        
    # === SENDER FUNCTIONS ===
    
    def can_send(self):
        """Check if sender window has space."""
        return self.next_seq_num < self.send_base + self.W
    
    def get_unacked_count(self):
        """Return number of unacknowledged frames."""
        return sum(1 for info in self.send_window.values() if not info['acked'])
    
    def create_frame(self, segment, current_time):
        """Create and register a new frame for transmission."""
        if not self.can_send():
            return None
        
        frame = Frame(self.next_seq_num, "DATA", segment.pack())
        
        self.send_window[self.next_seq_num] = {
            'frame': frame,
            'send_time': current_time,
            'acked': False,
            'retransmit_count': 0
        }
        
        self.next_seq_num += 1
        return frame
    
    def process_ack(self, ack_seq):
        """
        Process received ACK.
        Returns True if valid, False if duplicate/invalid.
        """
        if ack_seq not in self.send_window:
            return False
        
        if self.send_window[ack_seq]['acked']:
            return False  # Duplicate ACK
        
        self.send_window[ack_seq]['acked'] = True
        
        # Slide window
        while self.send_base in self.send_window and self.send_window[self.send_base]['acked']:
            del self.send_window[self.send_base]
            self.send_base += 1
        
        return True
    
    def get_timed_out_frames(self, current_time):
        """Return list of seq numbers that have timed out."""
        timed_out = []
        for seq, info in self.send_window.items():
            if not info['acked']:
                if current_time - info['send_time'] > self.timeout_interval:
                    timed_out.append(seq)
        return timed_out
    
    def prepare_retransmit(self, seq, current_time):
        """Prepare frame for retransmission, reset timer."""
        if seq in self.send_window:
            self.send_window[seq]['send_time'] = current_time
            self.send_window[seq]['retransmit_count'] += 1
            return self.send_window[seq]['frame']
        return None
    
    def all_acked(self):
        """Check if all sent frames are acknowledged."""
        return len(self.send_window) == 0
    
    # === RECEIVER FUNCTIONS ===
    
    def receive_frame(self, seq, payload):
        """
        Process received data frame (Selective Repeat).
        Returns: (in_order_payloads, ack_seq)
        - in_order_payloads: list of (seq, payload) ready for transport layer
        - ack_seq: sequence number to ACK
        """
        in_order = []
        
        # Check if within receiver window
        if self.recv_base <= seq < self.recv_base + self.W:
            # Buffer if not already received
            if seq not in self.recv_buffer:
                self.recv_buffer[seq] = payload
            
            # Collect in-order frames
            while self.recv_base in self.recv_buffer:
                in_order.append((self.recv_base, self.recv_buffer[self.recv_base]))
                del self.recv_buffer[self.recv_base]
                self.recv_base += 1
        
        return in_order, seq
    
    def get_recv_base(self):
        """Return receiver's next expected sequence."""
        return self.recv_base
