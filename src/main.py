import pandas as pd
import numpy as np
from engine import SimulationEngine
from config import W_VALUES, L_VALUES, TOTAL_DATA_SIZE

def run_experiment():
    print("Preparing 100 MB test data...")
    test_data = np.random.bytes(TOTAL_DATA_SIZE)
    
    results = []
    total_runs = len(W_VALUES) * len(L_VALUES) * 10
    run_num = 0
    
    # 360 Simulations (6W x 6L x 10 Seeds)
    for w in W_VALUES:
        for l in L_VALUES:
            for seed in range(10):
                run_num += 1
                print(f"\r[{run_num}/{total_runs}] W={w}, L={l}, Seed={seed}...", end="", flush=True)
                
                engine = SimulationEngine(W=w, L=l, seed=seed)
                total_time = engine.run(test_data)
                
                # Goodput: Only payload bytes / total time
                goodput_bps = (TOTAL_DATA_SIZE * 8) / total_time
                
                results.append({
                    "W": w,
                    "L": l,
                    "seed": seed,
                    "goodput": goodput_bps,
                    "goodput_mbps": goodput_bps / 1e6,
                    "total_time": total_time,
                    "retransmissions": engine.retransmissions,
                    "buffer_events": engine.buffer_events,
                    "delayed_acks": engine.delayed_acks
                })

    df = pd.DataFrame(results)
    df.to_csv("simulation_results.csv", index=False)
    
    # Print summary
    print("\n\n=== SIMULATION COMPLETE ===")
    print(f"Total runs: {total_runs}")
    print(f"Results saved to: simulation_results.csv")
    
    # Find optimal
    avg_results = df.groupby(['W', 'L'])['goodput_mbps'].mean().reset_index()
    optimal = avg_results.loc[avg_results['goodput_mbps'].idxmax()]
    print(f"\nOptimal: W={int(optimal['W'])}, L={int(optimal['L'])}, Avg Goodput={optimal['goodput_mbps']:.2f} Mbps")

if __name__ == "__main__":
    run_experiment()
