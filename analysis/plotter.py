import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm

def plot_goodput_surface_swapped(csv_file="simulation_results.csv"):
    # Load the simulation results
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: {csv_file} not found.")
        return

    # Average the goodput over 10 seeds
    avg_results = df.groupby(['W', 'L'])['goodput'].mean().reset_index()

    # Pivot the data
    # Index: W, Columns: L
    pivot_df = avg_results.pivot(index='W', columns='L', values='goodput')

    # --- Swapping Axes ---
    # We want W on the X-axis and L on the Y-axis
    X = pivot_df.index.values    # Window Size (W)
    Y = pivot_df.columns.values  # Payload Size (L)
    
    # Meshgrid creates the coordinate system
    # Z must be transposed (.T) to match the (Y, X) shape of meshgrid
    X_grid, Y_grid = np.meshgrid(X, Y)
    Z_grid = pivot_df.values.T 

    # Plotting
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')

    # Surface plot
    surf = ax.plot_surface(X_grid, Y_grid, Z_grid, cmap=cm.plasma,
                           linewidth=0.5, antialiased=True, alpha=0.9)

    # Optimal Point
    max_goodput = avg_results['goodput'].max()
    opt_row = avg_results[avg_results['goodput'] == max_goodput].iloc[0]
    opt_w = opt_row['W']
    opt_l = opt_row['L']

    # Mark the optimum on the new axes (X=W, Y=L)
    ax.scatter(opt_w, opt_l, max_goodput, color='red', s=150, marker='*', 
               label=f'Optimal: W={opt_w}, L={opt_l}\n{max_goodput/1e6:.2f} Mbps')

    # Labels (Updated to reflect the swap)
    ax.set_xlabel('Window Size (W)', fontsize=10, labelpad=10)
    ax.set_ylabel('Payload Size (L) [Bytes]', fontsize=10, labelpad=10)
    ax.set_zlabel('Goodput [bps]', fontsize=10, labelpad=10)
    ax.set_title('Selective Repeat Optimization', fontsize=14)

    # Adjust the viewing angle for better visibility
    # elevation = 30, azimuth = 45 (You can change these to rotate the plot)
    ax.view_init(elev=30, azim=225)

    fig.colorbar(surf, shrink=0.5, aspect=10, label='Goodput (bps)')
    plt.legend()
    plt.tight_layout()
    
    plt.savefig("goodput_3d.png", dpi=300)
    print(f"Plot saved. Optimum point remains at W={opt_w}, L={opt_l}")

if __name__ == "__main__":
    plot_goodput_surface_swapped()