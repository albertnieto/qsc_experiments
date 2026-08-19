# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

import numpy as np
import json
import os
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"
# Output directory for generated figures. Defaults to results/ so the script is
# self-contained; set QSC_PLOTS_OUTPUT_DIR to render elsewhere (e.g. a paper
# assets folder outside this repository).
OUTPUT_DIR = Path(os.environ.get("QSC_PLOTS_OUTPUT_DIR", RESULTS_DIR))


def load_evidence():
    """Load the versioned local evidence used to render both paper figures."""
    with (RESULTS_DIR / "full_framework_results.json").open() as handle:
        framework = json.load(handle)
    with (RESULTS_DIR / "scalability_results.json").open() as handle:
        scalability = json.load(handle)

    framework_results = {
        f"{index}. Channel {index}": framework[f"channel_{index}"]
        for index in range(1, 8)
    }
    plot_data = scalability["plot_data"]
    pqc_raw = [
        {"workers": workers, "time_ms": time_ms}
        for workers, time_ms in zip(
            plot_data["worker_counts"], plot_data["pqc_times"]
        )
    ]
    classical_raw = [
        {"workers": workers, "time_ms": time_ms}
        for workers, time_ms in zip(
            plot_data["worker_counts"], plot_data["classical_times"]
        )
    ]
    return framework_results, pqc_raw, classical_raw

def plot_protocols_cost(results):
    """Plot 1: Architectural Protocol Cost Breakdown (7 Channels)"""
    
    channels = list(results.keys())
    pqc_times = [data['pqc'] for data in results.values()]
    classical_times = [data['classical'] for data in results.values()]
    
    x = np.arange(len(channels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(8, 5))
    
    # Plot bars
    rects1 = ax.bar(x - width/2, pqc_times, width, label='PQC', color='#004C99', linewidth=0.5, edgecolor='black')
    rects2 = ax.bar(x + width/2, classical_times, width, label='Classical', color='#80BFFF', linewidth=0.5, edgecolor='black')
    
    # Labels
    ax.set_ylabel('Mean Latency (ms)', fontsize=9, fontweight='bold')
    ax.set_xlabel('Communication Channel', fontsize=9, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([f"{i+1}" for i in range(len(channels))], fontsize=8)
    ax.legend(fontsize=7, loc='upper left', framealpha=0.9)
    ax.grid(axis='y', linestyle='--', alpha=0.4, linewidth=0.5)
    ax.tick_params(axis='both', labelsize=8)
    
    plt.tight_layout(pad=0.5)
    plt.savefig(
        OUTPUT_DIR / "architectural_protocols_cost.png",
        dpi=300,
        bbox_inches="tight",
    )
    print("✅ Generated architectural_protocols_cost.png")

def plot_scalability_throughput(pqc_data, classical_data):
    """Plot 2: Scalability (Dual Y-Axis Line Plot)"""
    
    workers = np.array([d['workers'] for d in pqc_data])
    pqc_time = np.array([d['time_ms'] for d in pqc_data])
    classical_time = np.array([d['time_ms'] for d in classical_data])
    
    # Calculate Throughput (Req/s = N_Workers * N_Iterations / Total_Time_s)
    # Assuming the times represent the fan-out time for the N workers.
    pqc_throughput = (workers * 1000) / pqc_time
    classical_throughput = (workers * 1000) / classical_time

    fig, ax1 = plt.subplots(figsize=(8, 5))
    
    # --- Primary Y-Axis (Total Time) ---
    ax1.set_xlabel('Concurrent Workers', fontsize=9, fontweight='bold')
    ax1.set_ylabel('Processing Time (ms)', color='#004C99', fontsize=9, fontweight='bold')
    ax1.plot(workers, pqc_time, 'o-', color='#004C99', label='PQC Time', linewidth=2, markersize=6)
    ax1.plot(workers, classical_time, '^-', color='#80BFFF', label='Classical Time', linewidth=2, markersize=6)
    ax1.tick_params(axis='y', labelcolor='#004C99', labelsize=8)
    ax1.tick_params(axis='x', labelsize=8)
    ax1.grid(axis='both', linestyle='--', alpha=0.3, linewidth=0.5)
    ax1.set_xticks(workers)
    
    # --- Secondary Y-Axis (Throughput) ---
    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    ax2.set_ylabel('Throughput (Req/s)', color='red', fontsize=9, fontweight='bold')
    ax2.plot(workers, pqc_throughput, 's--', color='red', label='PQC Throughput', linewidth=1.5, markersize=5)
    ax2.plot(workers, classical_throughput, 'd--', color='orange', label='Classical Throughput', linewidth=1.5, markersize=5)
    ax2.tick_params(axis='y', labelcolor='red', labelsize=8)
    
    # Add a custom legend combining all lines
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=6, framealpha=0.9)

    fig.tight_layout(pad=0.5)
    plt.savefig(
        OUTPUT_DIR / "scalability_throughput.png",
        dpi=300,
        bbox_inches="tight",
    )
    print("✅ Generated scalability_throughput.png")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
    # Set environment for high-quality plots
    plt.style.use('default')
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.size'] = 8
    plt.rcParams['figure.dpi'] = 600
    plt.rcParams['lines.linewidth'] = 1.5
    plt.rcParams['axes.linewidth'] = 0.8
    
    framework_results, pqc_raw, classical_raw = load_evidence()
    plot_protocols_cost(framework_results)
    plot_scalability_throughput(pqc_raw, classical_raw)
    
    print("\n--- Plot Generation Complete ---")
    print(f"Files saved in: {OUTPUT_DIR}")
    print("----------------------------------")

if __name__ == "__main__":
    main()