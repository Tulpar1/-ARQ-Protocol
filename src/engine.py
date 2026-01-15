# engine.py - Event-Driven Simulation Engine with Cross-Layer Integration

import heapq
from config import *

class Event:
    """Simulation event with proper ordering."""
    _counter = 0
    
    def __init__(self, time, event_type, data=None):
        self.time = time
        self.type = event_type
        self.data = data
        Event._counter += 1
        self._order = Event._counter
    
    def __lt__(self, other):
        if self.time == other.time:
            return self._order < other._order
        return self.time < other.time


class SimulationEngine:
    def __init__(self, W, L, seed):
        # Local imports to avoid circular dependency
        from layers.physical import PhysicalLayer
        from layers.transport import TransportLayer
        from layers.link import LinkLayer
        
        self.W = W
        self.L = L
        
        # Initialize layers
        self.phy = PhysicalLayer(seed=seed)
        self.transport = TransportLayer(L)
        self.link = LinkLayer(W, timeout_interval=0.150)
        
        # Event queue
        self.events = []
        self.current_time = 0.0
        
        # Link serialization (Channel busy/free state)
        self.link_free_time = 0.0
        
        # App consumption rate (10 Mbps bit rate converted to Bytes/sec)
        self.app_rate = BIT_RATE / 8
        
        # Statistics
        self.retransmissions = 0
        self.buffer_events = 0
        self.total_delivered = 0
        self.delayed_acks = 0

    def schedule(self, delay, event_type, data=None):
        """Schedules a new event in the priority queue."""
        heapq.heappush(self.events, Event(self.current_time + delay, event_type, data))
    
    def run(self, total_data):
        """Main simulation loop: Runs until all segments are delivered to application."""
        
        segments = self.transport.segmentize(total_data)
        total_segments = len(segments)
        next_seg_idx = 0
        
        # Fixed sizes from config
        frame_bytes = LINK_HEADER_SIZE + TRANSPORT_HEADER_SIZE + self.L
        ack_bytes = LINK_HEADER_SIZE
        
        # Serialization delays
        tx_delay = (frame_bytes * 8) / BIT_RATE
        
        # Start application consumption loop
        self.schedule(0.001, 'APP_CONSUME')
        
        while self.link.get_recv_base() < total_segments:
            
            # 1. Backpressure Check: Combined buffer usage (Transport + Link Layer)
            # This ensures W=64, L=4096 will hit the 256KB limit during burst errors.
            link_buffer_usage = len(self.link.recv_buffer) * self.L
            total_buffer_usage = self.transport.current_buffer_usage + link_buffer_usage
            buffer_available = (self.transport.buffer_capacity - total_buffer_usage) >= self.L
            
            # 2. Sender: Transmit new frames if window and buffer allow
            if (next_seg_idx < total_segments and self.link.can_send() and buffer_available):
                segment = segments[next_seg_idx]
                tx_start = max(self.current_time, self.link_free_time)
                
                frame = self.link.create_frame(segment, tx_start)
                if frame is not None:
                    forward_delay = self.phy.calculate_delay(frame_bytes, direction="forward")
                    is_corrupted = self.phy.check_error(frame_bytes)
                    checksum = self.transport.compute_checksum(segment.data)
                    
                    self.schedule(tx_start - self.current_time + forward_delay, 'DATA_ARRIVE',
                        {'seq': frame.seq_num, 'payload': segment.data, 'corrupted': is_corrupted, 'checksum': checksum}
                    )
                    
                    self.link_free_time = tx_start + tx_delay
                    next_seg_idx += 1
            
            # 3. Handle Timeouts: Selective Retransmission
            timed_out = self.link.get_timed_out_frames(self.current_time)
            for seq in timed_out:
                self.retransmissions += 1
                frame = self.link.prepare_retransmit(seq, self.current_time)
                if frame:
                    tx_start = max(self.current_time, self.link_free_time)
                    forward_delay = self.phy.calculate_delay(frame_bytes, direction="forward")
                    is_corrupted = self.phy.check_error(frame_bytes)
                    
                    # Ensure original checksum is included in retransmission
                    orig_payload = segments[seq].data
                    orig_checksum = self.transport.compute_checksum(orig_payload)
                    
                    self.schedule(tx_start - self.current_time + forward_delay, 'DATA_ARRIVE',
                        {'seq': seq, 'payload': orig_payload, 'corrupted': is_corrupted, 'checksum': orig_checksum}
                    )
                    self.link_free_time = tx_start + tx_delay
            
            # 4. Event Processing
            if not self.events:
                self.current_time += 0.001 # Move clock if idle
                continue
                
            event = heapq.heappop(self.events)
            self.current_time = event.time
            
            if event.type == 'DATA_ARRIVE':
                self._handle_data_arrive(event.data, ack_bytes)
            
            elif event.type == 'ACK_ARRIVE':
                self._handle_ack_arrive(event.data['seq'], frame_bytes)
            
            elif event.type == 'APP_CONSUME':
                # Consumes data based on a 1ms tick
                self.transport.app_consume(int(self.app_rate * 0.001))
                self.schedule(0.001, 'APP_CONSUME')
            
            elif event.type == 'DELAYED_ACK':
                self._send_ack(event.data['seq'], ack_bytes)
        
        return self.current_time
    
    def _handle_data_arrive(self, data, ack_bytes):
        """Processes a data frame arriving at the receiver."""
        if data['corrupted']:
            return # Frame dropped due to BER
        
        seq = data['seq']
        payload = data['payload']
        checksum = data['checksum']
        
        # Step 1: Link Layer Processing
        # NOTE: link.receive_frame must be updated to store (payload, checksum) tuples!
        in_order_data, ack_seq = self.link.receive_frame(seq, payload, checksum)
        
        # Step 2: Delivery to Transport Layer with Integrity Check
        for s_seq, s_payload, s_checksum in in_order_data:
            success, _ = self.transport.receive_segment(s_seq, s_payload, s_checksum)
            if not success:
                self.buffer_events += 1 # Integrity fail or Buffer full
                return 

        # Step 3: Send ACK
        if self.transport.should_delay_ack():
            self.delayed_acks += 1
            self.schedule(0.010, 'DELAYED_ACK', {'seq': ack_seq}) # 10ms Backpressure
        else:
            self._send_ack(ack_seq, ack_bytes)

    def _send_ack(self, seq, ack_bytes):
        """Schedules the arrival of an ACK at the sender."""
        reverse_delay = self.phy.calculate_delay(ack_bytes, direction="reverse")
        self.schedule(reverse_delay, 'ACK_ARRIVE', {'seq': seq})

    def _handle_ack_arrive(self, seq, frame_bytes):
        """Process the ACK in the Link Layer with Fast Retransmit support."""
        trigger_fast_retransmit = self.link.process_ack(seq, self.current_time)
        
        # If 3 duplicate ACKs occur, retransmit the oldest unacked packet immediately
        if trigger_fast_retransmit:
            base_seq = self.link.send_base
            frame = self.link.prepare_retransmit(base_seq, self.current_time)
            if frame:
                self.retransmissions += 1
                # Schedule immediate retransmission
                tx_start = max(self.current_time, self.link_free_time)
                forward_delay = self.phy.calculate_delay(frame_bytes, direction="forward")
                is_corrupted = self.phy.check_error(frame_bytes)
                
                # Get original payload and checksum
                orig_payload = frame.payload[8:]  # Skip transport header
                orig_checksum = self.transport.compute_checksum(orig_payload)
                
                self.schedule(tx_start - self.current_time + forward_delay, 'DATA_ARRIVE',
                    {'seq': base_seq, 'payload': orig_payload, 'corrupted': is_corrupted, 'checksum': orig_checksum}
                )
                
                # Reset dup_ack_count to avoid repeated fast retransmits for same packet
                self.link.dup_ack_count = 0
