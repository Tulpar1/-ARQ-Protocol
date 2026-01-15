import time
from config import LINK_HEADER_SIZE
from models import Frame

class LinkLayer:
    def __init__(self, window_size, timeout_interval=0.2):
        """
        window_size (W): Sender and receiver window size.
        timeout_interval: Independent timeout duration for each frame.
        """
        self.W = window_size
        self.timeout_interval = timeout_interval
        
        # --- Sender Variables ---
        self.base = 0                       # Start of the window
        self.next_seq_num = 0               # Next sequence number to send
        self.send_window = {}               # {seq_num: {'frame': frame, 'timer': t, 'acked': bool}}
        
        # --- Receiver Variables ---
        self.expected_seq = 0               # First sequence number expected by the receiver
        self.receive_buffer = {}            # Buffer for out-of-order packets

    # --- Sender Functions ---

    def can_send(self):
        """Checks whether there is space in the window: next_seq < base + W."""
        return self.next_seq_num < self.base + self.W

    def send_frame(self, segment_obj, current_time):
        """Takes a transport segment, adds a link header, and records transmission info."""
        if self.can_send():
            # Create frame (Header: 24 bytes)
            new_frame = Frame(self.next_seq_num, "DATA", segment_obj.pack())
            
            # Store transmission info and start timer
            self.send_window[self.next_seq_num] = {
                'frame': new_frame,
                'send_time': current_time,
                'acked': False
            }
            
            self.next_seq_num += 1
            return new_frame
        return None

    def handle_ack(self, ack_num):
        """Processes ACKs received from the receiver and slides the window."""
        if ack_num in self.send_window:
            self.send_window[ack_num]['acked'] = True
            
            # Selective Repeat: Slide the window if the base frame is acknowledged
            while self.base in self.send_window and self.send_window[self.base]['acked']:
                del self.send_window[self.base]
                self.base += 1

    def check_timeouts(self, current_time):
        """Finds timed-out packets (only the relevant packet is retransmitted)."""
        timeouts = []
        for seq_num, info in self.send_window.items():
            if not info['acked'] and (current_time - info['send_time'] > self.timeout_interval):
                timeouts.append(seq_num)
                # Reset timer
                info['send_time'] = current_time
        return timeouts

    # --- Receiver Functions ---

    def receive_data_frame(self, frame_obj):
        """
        Accepts out-of-order packets and buffers them.
        Returns in-order packets to be delivered to the transport layer.
        """
        seq = frame_obj.seq_num
        
        # If the packet is within the window, buffer it
        if self.expected_seq <= seq < self.expected_seq + self.W:
            if seq not in self.receive_buffer:
                self.receive_buffer[seq] = frame_obj.payload
        
        # If the expected packet arrives, deliver all consecutive ready packets
        ready_payloads = []
        while self.expected_seq in self.receive_buffer:
            ready_payloads.append(self.receive_buffer.pop(self.expected_seq))
            self.expected_seq += 1
            
        return ready_payloads  # Data to be passed to the transport layer
