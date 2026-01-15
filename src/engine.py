import heapq
from config import *

class SimulationEngine:
    def __init__(self, W, L, seed):
        # Initialize Layers
        from layers.physical import PhysicalLayer
        from layers.transport import TransportLayer
        from layers.link import LinkLayer
        
        self.phy = PhysicalLayer(seed=seed)
        self.transport = TransportLayer(L)
        self.link = LinkLayer(W, timeout_interval=0.150) # RTT-based safe timeout
        
        self.current_time = 0.0
        self.event_count = 0
        self.event_queue = [] # heapq (priority queue) as (time, event_type, data)
        self.is_finished = False
        
        # Statistics
        self.retransmissions = 0
        self.buffer_events = 0
        self.total_delivered_bytes = 0

    def add_event(self, event_time, event_type, data=None):
        """Adds a new event to the queue with a tie-breaker."""
        self.event_count += 1
        heapq.heappush(self.event_queue, (event_time, self.event_count, event_type, data))

    def run(self, total_data):
        """Runs the simulation until 100 MB of data is sent."""
        # 1. Segment the data
        segments = self.transport.segmentize(total_data)
        seg_idx = 0
        
        while seg_idx < len(segments) or self.event_queue or self.link.send_window:
            # A. SENDING: If window is available and data exists
            # Backpressure Control: Stop if the buffer is full
            while self.link.can_send() and seg_idx < len(segments) and not self.transport.is_backpressure_required():
                segment = segments[seg_idx]
                frame = self.link.send_frame(segment, self.current_time)
                
                # Send to Physical Channel
                delay = self.phy.calculate_delay(len(frame.pack()), direction="forward")
                is_corrupted = self.phy.check_error(len(frame.pack()))
                
                # Add Arrival Event
                self.add_event(self.current_time + delay, "DATA_ARRIVAL", (frame, is_corrupted))
                seg_idx += 1

            # B. TIMEOUT CONTROL
            timeouts = self.link.check_timeouts(self.current_time)
            for seq in timeouts:
                self.retransmissions += 1
                frame_to_resend = self.link.send_window[seq]['frame']
                delay = self.phy.calculate_delay(len(frame_to_resend.pack()), direction="forward")
                is_corrupted = self.phy.check_error(len(frame_to_resend.pack()))
                self.add_event(self.current_time + delay, "DATA_ARRIVAL", (frame_to_resend, is_corrupted))

            # C. PROCESS EVENTS
            if not self.event_queue:
                break
                
            event_time, _, event_type, data = heapq.heappop(self.event_queue)
            self.current_time = event_time

            if event_type == "DATA_ARRIVAL":
                frame, is_corrupted = data
                if not is_corrupted: # If the frame reached successfully
                    # Link Layer Receiver Operations
                    received_payloads = self.link.receive_data_frame(frame)
                    
                    # Transfer to Transport Layer Buffer
                    for payload in received_payloads:
                        from models import Segment # Create sample segment object
                        # Simply transport seq should be extracted from payload
                        # self.transport.receive_segment(...)
                        pass
                    
                    # Send ACK back (Reverse Delay + 2ms Proc)
                    ack_delay = self.phy.calculate_delay(24, direction="reverse") # ACK 24-byte link header
                    self.add_event(self.current_time + ack_delay, "ACK_ARRIVAL", frame.seq_num)

            elif event_type == "ACK_ARRIVAL":
                self.link.handle_ack(data)

        return self.current_time # Total simulation time
