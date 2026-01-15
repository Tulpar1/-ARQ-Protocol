# link.py - Link Layer with Selective Repeat ARQ + Adaptive Timeout

from config import LINK_HEADER_SIZE
from models import Frame
import math

class LinkLayer:
    def __init__(self, window_size, initial_timeout=0.150):
        self.W = window_size
        
        # === SENDER STATE ===
        self.send_base = 0
        self.next_seq_num = 0
        self.send_window = {}  # {seq: {'frame': Frame, 'send_time': float, 'acked': bool, 'retransmitted': bool}}
        
        # === ADAPTIVE TIMEOUT (Jacobson's Algorithm) ===
        self.estimated_rtt = initial_timeout
        self.dev_rtt = initial_timeout / 2
        self.timeout_interval = initial_timeout
        self.alpha = 0.125
        self.beta = 0.25
        
        # === FAST RETRANSMIT STATE ===
        self.last_ack_received = -1
        self.dup_ack_count = 0
        
        # === RECEIVER STATE ===
        self.recv_base = 0
        self.recv_buffer = {}  # {seq: (payload, checksum)} for out-of-order
        self.pending_acks = []
        
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
            'retransmitted': False
        }
        
        self.next_seq_num += 1
        return frame
    
    def process_ack(self, ack_seq, current_time=None):
        """
        Processes an ACK and updates RTT/Timeout logic.
        Returns True if Fast Retransmit is triggered (3 duplicate ACKs).
        """
        # 1. Fast Retransmit Logic: Check for Duplicate ACKs
        if ack_seq == self.last_ack_received:
            self.dup_ack_count += 1
        else:
            self.last_ack_received = ack_seq
            self.dup_ack_count = 0

        # 2. Update Window State
        if ack_seq in self.send_window:
            # Only update RTT for packets that were NOT retransmitted (Karn's Algorithm)
            if current_time is not None and not self.send_window[ack_seq]['retransmitted']:
                sample_rtt = current_time - self.send_window[ack_seq]['send_time']
                self._update_rto(sample_rtt)
            
            self.send_window[ack_seq]['acked'] = True
            
            # Slide window
            while self.send_base in self.send_window and self.send_window[self.send_base]['acked']:
                del self.send_window[self.send_base]
                self.send_base += 1
                
        # Return True if Fast Retransmit is triggered (3 duplicate ACKs)
        return self.dup_ack_count >= 3

    def _update_rto(self, sample_rtt):
        """Jacobson's Algorithm for RTO calculation."""
        self.estimated_rtt = (1 - self.alpha) * self.estimated_rtt + self.alpha * sample_rtt
        self.dev_rtt = (1 - self.beta) * self.dev_rtt + self.beta * abs(sample_rtt - self.estimated_rtt)
        self.timeout_interval = self.estimated_rtt + 4 * self.dev_rtt
        # Safety bound: cap timeout between 20ms and 500ms
        self.timeout_interval = max(0.020, min(self.timeout_interval, 0.500))

    def get_timed_out_frames(self, current_time):
        """Return list of seq numbers that have timed out."""
        timed_out = []
        for seq, info in self.send_window.items():
            if not info['acked']:
                if current_time - info['send_time'] > self.timeout_interval:
                    timed_out.append(seq)
        return timed_out
    
    def prepare_retransmit(self, seq, current_time):
        """Marks frame as retransmitted and resets timer."""
        if seq in self.send_window:
            self.send_window[seq]['send_time'] = current_time
            self.send_window[seq]['retransmitted'] = True
            return self.send_window[seq]['frame']
        return None
    
    def all_acked(self):
        """Check if all sent frames are acknowledged."""
        return len(self.send_window) == 0
    
    # === RECEIVER FUNCTIONS ===
    
    def receive_frame(self, seq, payload, checksum):
        """
        Process received data frame (Selective Repeat).
        Returns: (in_order_data, ack_seq)
        - in_order_data: list of (seq, payload, checksum) ready for transport layer
        - ack_seq: sequence number to ACK
        """
        in_order = []
        if self.recv_base <= seq < self.recv_base + self.W:
            if seq not in self.recv_buffer:
                self.recv_buffer[seq] = (payload, checksum)
            
            while self.recv_base in self.recv_buffer:
                p, c = self.recv_buffer[self.recv_base]
                in_order.append((self.recv_base, p, c))
                del self.recv_buffer[self.recv_base]
                self.recv_base += 1
        return in_order, seq
    
    def get_recv_base(self):
        """Return receiver's next expected sequence."""
        return self.recv_base
