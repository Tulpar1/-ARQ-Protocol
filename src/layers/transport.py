from config import RECEIVER_BUFFER_SIZE, TRANSPORT_HEADER_SIZE
from models import Segment

class TransportLayer:
    def __init__(self, segment_payload_size):
        """
        L: Application data chunk size (Payload size)
        """
        self.L = segment_payload_size
        self.buffer_capacity = RECEIVER_BUFFER_SIZE  # 256 KB 
        
        # Receiver-side variables
        self.receive_buffer = {}  # Stored as {seq_num: data}
        self.current_buffer_usage = 0
        
    # --- Sender Functions ---
    
    def segmentize(self, total_data):
        """
        Splits 100 MB of data into chunks of size L and
        creates Segment objects by adding an 8-byte header to each. 
        """
        segments = []
        # Iterate over the data in L-byte chunks
        for i in range(0, len(total_data), self.L):
            chunk = total_data[i : i + self.L]
            seq_num = i // self.L
            # Create segment (uses the structure in models.py)
            segments.append(Segment(seq_num, chunk))
        return segments

    # --- Receiver Functions ---

    def receive_segment(self, segment_obj):
        """
        Accepts a segment received from the link layer.
        Returns False to signal backpressure if the buffer is full. 
        """
        # Buffer occupancy check
        # Assignment rule: Apply pressure to the link layer if the buffer is full.
        if self.current_buffer_usage + len(segment_obj.data) <= self.buffer_capacity:
            if segment_obj.seq_num not in self.receive_buffer:
                self.receive_buffer[segment_obj.seq_num] = segment_obj.data
                self.current_buffer_usage += len(segment_obj.data)
            return True  # Segment successfully added to the buffer
        
        return False  # BUFFER FULL! (Backpressure should be triggered)

    def is_backpressure_required(self):
        """
        The link layer should check this function and
        slow down or stop transmission accordingly. 
        """
        return self.current_buffer_usage >= self.buffer_capacity

    def app_read_buffer(self):
        """
        Simulates the application layer reading and clearing data from the buffer.
        In a real scenario, this operation frees buffer space and allows the flow to continue.
        """
        # This function will be used in the simulation to manage buffer occupancy
        # For example: After a certain time, you may clear part of the buffer.
        pass

    def get_full_data(self):
        """
        Performs reassembly by combining all segments and checking integrity.
        """
        sorted_indices = sorted(self.receive_buffer.keys())
        return b"".join([self.receive_buffer[i] for i in sorted_indices])
