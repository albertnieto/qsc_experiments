# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Generate plots for scalability analysis.
"""
import json
import matplotlib.pyplot as plt
from results_paths import result_path
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend


def load_scalability_results(filepath: str = str(result_path("scalability_results.json"))):
    """Load scalability results."""
    with open(filepath, "r") as f:
        return json.load(f)


def plot_total_time(data: dict, output_path: str):
    """Plot total time vs number of workers."""
    plot_data = data["plot_data"]
    
    plt.figure(figsize=(10, 6))
    plt.plot(plot_data["worker_counts"], plot_data["pqc_times"], 
             marker='o', linewidth=2, markersize=8, label='PQC (ML-DSA-65)')
    plt.plot(plot_data["worker_counts"], plot_data["classical_times"], 
             marker='s', linewidth=2, markersize=8, label='Classical (Ed25519)')
    
    plt.xlabel('Number of Workers', fontsize=12)
    plt.ylabel('Total Time (ms)', fontsize=12)
    plt.title('Fan-Out Scalability: Total Time to Process All Workers', fontsize=14, fontweight='bold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def plot_throughput(data: dict, output_path: str):
    """Plot throughput vs number of workers."""
    plot_data = data["plot_data"]
    
    plt.figure(figsize=(10, 6))
    plt.plot(plot_data["worker_counts"], plot_data["pqc_throughput"], 
             marker='o', linewidth=2, markersize=8, label='PQC (ML-DSA-65)')
    plt.plot(plot_data["worker_counts"], plot_data["classical_throughput"], 
             marker='s', linewidth=2, markersize=8, label='Classical (Ed25519)')
    
    plt.xlabel('Number of Workers', fontsize=12)
    plt.ylabel('Throughput (requests/sec)', fontsize=12)
    plt.title('Fan-Out Scalability: System Throughput', fontsize=14, fontweight='bold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def plot_overhead(data: dict, output_path: str):
    """Plot PQC overhead percentage vs number of workers."""
    plot_data = data["plot_data"]
    
    overhead = [((pqc / classical) - 1) * 100 
                for pqc, classical in zip(plot_data["pqc_times"], plot_data["classical_times"])]
    
    plt.figure(figsize=(10, 6))
    plt.plot(plot_data["worker_counts"], overhead, 
             marker='o', linewidth=2, markersize=8, color='#d62728')
    
    plt.xlabel('Number of Workers', fontsize=12)
    plt.ylabel('PQC Overhead (%)', fontsize=12)
    plt.title('PQC Performance Overhead vs Classical', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def plot_time_per_worker(data: dict, output_path: str):
    """Plot average time per worker (scaling efficiency)."""
    pqc_results = data["pqc_results"]
    classical_results = data["classical_results"]
    
    worker_counts = [r["num_workers"] for r in pqc_results]
    pqc_per_worker = [r["mean_time_ms"] / r["num_workers"] for r in pqc_results]
    classical_per_worker = [r["mean_time_ms"] / r["num_workers"] for r in classical_results]
    
    plt.figure(figsize=(10, 6))
    plt.plot(worker_counts, pqc_per_worker, 
             marker='o', linewidth=2, markersize=8, label='PQC (ML-DSA-65)')
    plt.plot(worker_counts, classical_per_worker, 
             marker='s', linewidth=2, markersize=8, label='Classical (Ed25519)')
    
    plt.xlabel('Number of Workers', fontsize=12)
    plt.ylabel('Time per Worker (ms)', fontsize=12)
    plt.title('Scaling Efficiency: Average Time per Worker', fontsize=14, fontweight='bold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def plot_combined(data: dict, output_path: str):
    """Create combined 2x2 subplot figure."""
    plot_data = data["plot_data"]
    pqc_results = data["pqc_results"]
    classical_results = data["classical_results"]
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Total Time
    ax1.plot(plot_data["worker_counts"], plot_data["pqc_times"], 
             marker='o', linewidth=2, markersize=6, label='PQC')
    ax1.plot(plot_data["worker_counts"], plot_data["classical_times"], 
             marker='s', linewidth=2, markersize=6, label='Classical')
    ax1.set_xlabel('Number of Workers')
    ax1.set_ylabel('Total Time (ms)')
    ax1.set_title('Total Processing Time')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Throughput
    ax2.plot(plot_data["worker_counts"], plot_data["pqc_throughput"], 
             marker='o', linewidth=2, markersize=6, label='PQC')
    ax2.plot(plot_data["worker_counts"], plot_data["classical_throughput"], 
             marker='s', linewidth=2, markersize=6, label='Classical')
    ax2.set_xlabel('Number of Workers')
    ax2.set_ylabel('Throughput (req/s)')
    ax2.set_title('System Throughput')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Overhead
    overhead = [((pqc / classical) - 1) * 100 
                for pqc, classical in zip(plot_data["pqc_times"], plot_data["classical_times"])]
    ax3.plot(plot_data["worker_counts"], overhead, 
             marker='o', linewidth=2, markersize=6, color='#d62728')
    ax3.set_xlabel('Number of Workers')
    ax3.set_ylabel('PQC Overhead (%)')
    ax3.set_title('Performance Overhead')
    ax3.grid(True, alpha=0.3)
    ax3.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    
    # Plot 4: Time per Worker
    worker_counts = [r["num_workers"] for r in pqc_results]
    pqc_per_worker = [r["mean_time_ms"] / r["num_workers"] for r in pqc_results]
    classical_per_worker = [r["mean_time_ms"] / r["num_workers"] for r in classical_results]
    ax4.plot(worker_counts, pqc_per_worker, 
             marker='o', linewidth=2, markersize=6, label='PQC')
    ax4.plot(worker_counts, classical_per_worker, 
             marker='s', linewidth=2, markersize=6, label='Classical')
    ax4.set_xlabel('Number of Workers')
    ax4.set_ylabel('Time per Worker (ms)')
    ax4.set_title('Scaling Efficiency')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def main():
    """Generate all plots."""
    print("="*60)
    print("GENERATING SCALABILITY PLOTS")
    print("="*60 + "\n")
    
    try:
        data = load_scalability_results()
    except FileNotFoundError:
        print("Error: scalability_results.json not found. Run benchmark_scalability.py first.")
        return
    
    plot_total_time(data, str(result_path("plot_total_time.png")))
    plot_throughput(data, str(result_path("plot_throughput.png")))
    plot_overhead(data, str(result_path("plot_overhead.png")))
    plot_time_per_worker(data, str(result_path("plot_time_per_worker.png")))
    plot_combined(data, str(result_path("plot_combined.png")))
    
    print("\n" + "="*60)
    print("All plots generated successfully!")
    print("="*60)


if __name__ == "__main__":
    main()
