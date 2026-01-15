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
        
        # Link serialization
        self.link_free_time = 0.0
        
        # App consumption rate (10 Mbps)
        self.app_rate = BIT_RATE / 8  # bytes/sec
        
        # Statistics
        self.retransmissions = 0
        self.buffer_events = 0
        self.total_delivered = 0
        self.delayed_acks = 0

    def schedule(self, delay, event_type, data=None):
        """Schedule an event."""
        heapq.heappush(self.events, Event(self.current_time + delay, event_type, data))
    
    def run(self, total_data):
        """Run simulation until all data is delivered."""
        
        # Segment data
        segments = self.transport.segmentize(total_data)
        total_segments = len(segments)
        next_seg_idx = 0
        
        # Frame size for calculations
        frame_bytes = LINK_HEADER_SIZE + TRANSPORT_HEADER_SIZE + self.L
        ack_bytes = LINK_HEADER_SIZE
        
        # Delays
        tx_delay = (frame_bytes * 8) / BIT_RATE
        ack_tx_delay = (ack_bytes * 8) / BIT_RATE
        
        # Schedule initial app consumption
        self.schedule(0.001, 'APP_CONSUME')
        
        # Main loop
        while self.link.recv_base < total_segments:
            
            # Send new frames if possible
            while (next_seg_idx < total_segments and 
                   self.link.can_send() and 
                   self.transport.can_accept(self.L)):
                
                segment = segments[next_seg_idx]
                tx_start = max(self.current_time, self.link_free_time)
                
                frame = self.link.create_frame(segment, tx_start)
                if frame is None:
                    break
                
                # Calculate arrival time
                forward_delay = self.phy.calculate_delay(frame_bytes, direction="forward")
                arrival_time = tx_start + forward_delay
                
                # Check corruption
                is_corrupted = self.phy.check_error(frame_bytes)
                
                # Compute checksum for integrity verification
                checksum = self.transport.compute_checksum(segment.data)
                
                # Schedule arrival
                heapq.heappush(self.events, Event(
                    arrival_time, 'DATA_ARRIVE',
                    {'seq': frame.seq_num, 'payload': segment.data, 'corrupted': is_corrupted, 'checksum': checksum}
                ))
                
                # Update link free time
                self.link_free_time = tx_start + tx_delay
                next_seg_idx += 1
            
            # Check timeouts
            timed_out = self.link.get_timed_out_frames(self.current_time)
            for seq in timed_out:
                self.retransmissions += 1
                frame = self.link.prepare_retransmit(seq, self.current_time)
                if frame:
                    tx_start = max(self.current_time, self.link_free_time)
                    forward_delay = self.phy.calculate_delay(frame_bytes, direction="forward")
                    is_corrupted = self.phy.check_error(frame_bytes)
                    
                    # Get original payload
                    payload_data = segments[seq].data if seq < len(segments) else b''
                    
                    heapq.heappush(self.events, Event(
                        tx_start + forward_delay, 'DATA_ARRIVE',
                        {'seq': seq, 'payload': payload_data, 'corrupted': is_corrupted}
                    ))
                    self.link_free_time = tx_start + tx_delay
            
            # Process next event
            if not self.events:
                # No events, advance to next timeout or link free
                next_timeout = float('inf')
                for seq, info in self.link.send_window.items():
                    if not info['acked']:
                        next_timeout = min(next_timeout, info['send_time'] + self.link.timeout_interval)
                
                if next_timeout < float('inf'):
                    self.current_time = next_timeout
                else:
                    self.current_time += 0.001
                continue
            
            event = heapq.heappop(self.events)
            self.current_time = event.time
            
            if event.type == 'DATA_ARRIVE':
                self._handle_data_arrive(event.data, ack_bytes)
            
            elif event.type == 'ACK_ARRIVE':
                self.link.process_ack(event.data['seq'])
            
            elif event.type == 'APP_CONSUME':
                # App consumes data from transport buffer
                consumed = self.transport.app_consume(int(self.app_rate * 0.001))
                self.total_delivered += consumed
                # Reschedule
                self.schedule(0.001, 'APP_CONSUME')
            
            elif event.type == 'DELAYED_ACK':
                # Send delayed ACK
                seq = event.data['seq']
                reverse_delay = self.phy.calculate_delay(ack_bytes, direction="reverse")
                heapq.heappush(self.events, Event(
                    self.current_time + reverse_delay, 'ACK_ARRIVE', {'seq': seq}
                ))
        
        return self.current_time
    
    def _handle_data_arrive(self, data, ack_bytes):
        """Handle data frame arrival at receiver."""
        
        if data['corrupted']:
            return  # Corrupted at physical layer, no ACK
        
        seq = data['seq']
        payload = data['payload']
        checksum = data.get('checksum')  # Get checksum if present
        
        # Process at link layer
        in_order_segments, ack_seq = self.link.receive_frame(seq, payload)
        
        # Deliver to transport layer with integrity check
        for seg_seq, seg_payload in in_order_segments:
            success, should_ack_now = self.transport.receive_segment(seg_seq, seg_payload, checksum)
            if not success:
                self.buffer_events += 1
                return  # Integrity failed or buffer full, no ACK
        
        # Send ACK (possibly delayed)
        if self.transport.should_delay_ack():
            self.delayed_acks += 1
            self.schedule(0.010, 'DELAYED_ACK', {'seq': ack_seq})  # 10ms delay
        else:
            reverse_delay = self.phy.calculate_delay(ack_bytes, direction="reverse")
            heapq.heappush(self.events, Event(
                self.current_time + reverse_delay, 'ACK_ARRIVE', {'seq': ack_seq}
            ))
