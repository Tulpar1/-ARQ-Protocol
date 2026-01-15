# config.py

# Physical Layer Parameters
BIT_RATE = 10 * 10**6  # 10 Mbps 
FORWARD_PROP_DELAY = 0.040  # 40 ms 
REVERSE_PROP_DELAY = 0.010  # 10 ms 
PROCESSING_DELAY = 0.002    # 2 ms 


P_G_TO_B = 0.002
P_B_TO_G = 0.05
BER_GOOD = 1e-6
BER_BAD = 5e-3

# Layer Constraints
TRANSPORT_HEADER_SIZE = 8   # Byte 
LINK_HEADER_SIZE = 24      # Byte 
RECEIVER_BUFFER_SIZE = 256 * 1024  # 256 KB 

# Experiment Parameters
W_VALUES = [2, 4, 8, 16, 32, 64]
L_VALUES = [128, 256, 512, 1024, 2048, 4096]
TOTAL_DATA_SIZE = 100 * 1024 * 1024  # 100 MB 