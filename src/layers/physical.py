import random
from config import *

class PhysicalLayer:
    def __init__(self, seed=None):
        """
        Initializes the physical layer.
        A different seed is used for each scenario to change the error distribution.
        """
        if seed is not None:
            random.seed(seed)
        
        # Initially the channel is in 'GOOD' state
        self.current_state = "GOOD"
        
        # Fixed Parameters (from config.py)
        self.bit_rate = BIT_RATE             # 10 Mbps
        self.p_gb = P_G_TO_B                 # G -> B transition: 0.002
        self.p_bg = P_B_TO_G                 # B -> G transition: 0.05
        self.ber_good = BER_GOOD             # 1e-6
        self.ber_bad = BER_BAD               # 5e-3

    def _update_state(self):
        """
        Gilbert-Elliot State Transition: Updates the channel state after each frame transmission.
        """
        r = random.random()
        if self.current_state == "GOOD":
            if r < self.p_gb:
                self.current_state = "BAD"
        else:
            if r < self.p_bg:
                self.current_state = "GOOD"

    def calculate_delay(self, frame_size_bytes, direction="forward"):
        """
        Total Delay = Transmission Delay + Propagation Delay + Processing Delay
        """
        # 1. Transmission Delay (L_bits / R)
        tx_delay = (frame_size_bytes * 8) / self.bit_rate
        
        # 2. Propagation Delay (Depends on direction)
        prop_delay = FORWARD_PROP_DELAY if direction == "forward" else REVERSE_PROP_DELAY
        
        # 3. Processing Delay (Per frame)
        proc_delay = PROCESSING_DELAY
        
        return tx_delay + prop_delay + proc_delay

    def check_error(self, frame_size_bytes):
        """
        Determines whether the frame is corrupted according to the Gilbert-Elliot model.
        """
        # First update channel state (for burst effect)
        self._update_state()
        
        # Select the BER value of the current state
        ber = self.ber_good if self.current_state == "GOOD" else self.ber_bad
        
        # Total number of bits in the frame
        num_bits = frame_size_bytes * 8
        
        # Probability of the frame reaching error-free: P_success = (1 - BER)^N
        p_success = (1 - ber) ** num_bits
        
        # If random number is greater than p_success, the frame is corrupted
        return random.random() > p_success