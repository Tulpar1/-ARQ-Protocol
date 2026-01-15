import pandas as pd
import numpy as np
import os
from engine import SimulationEngine
from config import W_VALUES, L_VALUES, TOTAL_DATA_SIZE

def run_experiment():
    # 1. Generate 100 MB of Random Data (Phase 1 Input)
    print("Preparing 100 MB test data...")
    # Generate 100 MB of data using np.random.bytes
    test_data = np.random.bytes(TOTAL_DATA_SIZE)
    
    results = []
    
    # 2. Loop for 360 Simulations (6W x 6L x 10 Seeds)
    for w in W_VALUES:  # [2, 4, 8, 16, 32, 64]
        for l in L_VALUES:  # [128, 256, 512, 1024, 2048, 4096]
            print(f"\nStarting scenario: W={w}, L={l}")
            
            for seed in range(10):  # 10 different RNG seeds for each pair
                print(f"  Run {seed+1}/10...", end="\r")
                
                # Set up and run the simulation engine
                engine = SimulationEngine(W=w, L=l, seed=seed)
                total_time = engine.run(test_data)
                
                # Goodput Calculation: Delivered Bytes / Total Time
                # Only application data is considered (headers excluded)
                goodput_bps = (TOTAL_DATA_SIZE * 8) / total_time
                
                # Save metrics (for Phase 2 Gemini Analysis)
                results.append({
                    "W": w,
                    "L": l,
                    "run_id": seed,
                    "goodput": goodput_bps,
                    "retransmissions": engine.retransmissions,
                    "avg_rtt": total_time / (TOTAL_DATA_SIZE / l),  # Simplified RTT estimation
                    "utilization": (TOTAL_DATA_SIZE * 8 / 10e6) / total_time,
                    "buffer_events": engine.buffer_events
                })

    # 3. Save Results as CSV
    df = pd.DataFrame(results)
    df.to_csv("simulation_results.csv", index=False)
    print("\n\nSimulation completed! 'simulation_results.csv' file has been created.")

if __name__ == "__main__":
    run_experiment()
