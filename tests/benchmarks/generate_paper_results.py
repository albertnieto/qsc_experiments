# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Generate formatted results for paper publication.
"""
import json
from results_paths import result_path
import sys
from pathlib import Path


def operation_label(operation: str) -> str:
    """Return a publication label that reflects the measured operation."""
    if operation == "key_generation":
        return "Full Agent Identity Generation"
    return operation.replace("_", " ").title()


def load_results(filepath: str = str(result_path("benchmark_results.json"))):
    """Load benchmark results."""
    with open(filepath, "r") as f:
        return json.load(f)


def generate_latex_table(data: dict):
    """Generate LaTeX table for paper."""
    summary = data["summary"]
    
    print("\n% LaTeX Table - Copy to paper")
    print("\\begin{table}[h]")
    print("\\centering")
    print("\\caption{QSC Agent Identity and Protocol Performance Metrics}")
    print("\\begin{tabular}{lrrrr}")
    print("\\hline")
    print("Operation & Count & Mean (ms) & Min (ms) & Max (ms) \\\\")
    print("\\hline")
    
    for op, stats in summary.items():
        print(f"{operation_label(op)} & {stats['count']} & "
              f"{stats['mean_ms']:.2f} & {stats['min_ms']:.2f} & {stats['max_ms']:.2f} \\\\")
    
    print("\\hline")
    print("\\end{tabular}")
    print("\\end{table}\n")


def generate_markdown_table(data: dict):
    """Generate Markdown table."""
    summary = data["summary"]
    
    print("\n## Performance Results\n")
    print("| Operation | Count | Mean (ms) | Min (ms) | Max (ms) |")
    print("|-----------|-------|-----------|----------|----------|")
    
    for op, stats in summary.items():
        print(f"| {operation_label(op)} | {stats['count']} | "
              f"{stats['mean_ms']:.2f} | {stats['min_ms']:.2f} | {stats['max_ms']:.2f} |")
    print()


def generate_key_findings(data: dict):
    """Generate key findings summary."""
    summary = data["summary"]
    
    print("\n## Key Findings for Paper\n")
    
    if "key_generation" in summary:
        kg = summary["key_generation"]
        print(
            "1. **Full Agent Identity Generation**: Average "
            f"{kg['mean_ms']:.2f}ms per ML-DSA-65 + ML-KEM-768 identity"
        )
    
    if "sign_message" in summary:
        sign = summary["sign_message"]
        print(f"2. **Signing**: Average {sign['mean_ms']:.2f}ms per signature")
    
    if "verify_signature" in summary:
        verify = summary["verify_signature"]
        print(f"3. **Verification**: Average {verify['mean_ms']:.2f}ms per verification")
    
    if "handshake_full" in summary:
        hs = summary["handshake_full"]
        print(f"4. **Handshake**: Average {hs['mean_ms']:.2f}ms for complete authentication")
    
    if "qrng_query_id" in summary:
        qid = summary["qrng_query_id"]
        print(f"5. **QRNG Query ID**: Average {qid['mean_ms']:.4f}ms ({1000/qid['mean_ms']:.0f} IDs/sec)")
    
    if "qkd_establish_key" in summary:
        est = summary["qkd_establish_key"]
        print(f"6. **QKD Key Establishment**: Average {est['mean_ms']:.4f}ms")
    
    if "query_delegation_full" in summary:
        qd = summary["query_delegation_full"]
        throughput = 1000 / qd['mean_ms']
        print(f"7. **Query Delegation**: Average {qd['mean_ms']:.2f}ms end-to-end")
        print(f"8. **Throughput**: ~{throughput:.2f} secure queries/second")
    
    print()


def load_comparative_results(filepath: str = str(result_path("comparative_results.json"))):
    """Load comparative benchmark results."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def load_scalability_results(filepath: str = str(result_path("scalability_results.json"))):
    """Load scalability benchmark results."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def load_security_results(filepath: str = str(result_path("security_results.json"))):
    """Load security benchmark results."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def generate_comparative_analysis(data: dict):
    """Generate comparative analysis table."""
    if not data:
        return
    
    summary = data["summary"]
    
    print("\n## Comparative Analysis: PQC vs Classical\n")
    print("### End-to-End Performance\n")
    print("| Metric | PQC (ML-DSA-65) | Classical (Ed25519) | Overhead |")
    print("|--------|-----------------|---------------------|----------|")
    
    comparisons = [
        ("Key Generation", "pqc_keygen", "classical_keygen"),
        ("Signing", "pqc_sign", "classical_sign"),
        ("Verification", "pqc_verify", "classical_verify"),
        ("Query Delegation", "pqc_query_delegation", "classical_query_delegation"),
    ]
    
    for label, pqc_key, classical_key in comparisons:
        if pqc_key in summary and classical_key in summary:
            pqc_val = summary[pqc_key]["mean_ms"]
            classical_val = summary[classical_key]["mean_ms"]
            overhead = ((pqc_val / classical_val) - 1) * 100
            print(
                f"| {label} | {pqc_val:.3f} ms | "
                f"{classical_val:.3f} ms | {overhead:+.1f}% |"
            )
    
    print("\n### Cryptographic Artifact Sizes\n")
    print("| Artifact | PQC | Classical | Overhead |")
    print("|----------|-----|-----------|----------|")
    
    size_comparisons = [
        ("Public Key", "pqc_pubkey_size", "classical_pubkey_size"),
        ("Signature", "pqc_sig_size", "classical_sig_size"),
    ]
    
    for label, pqc_key, classical_key in size_comparisons:
        if pqc_key in summary and classical_key in summary:
            pqc_val = summary[pqc_key]["total_bytes"] / summary[pqc_key]["count"]
            classical_val = summary[classical_key]["total_bytes"] / summary[classical_key]["count"]
            overhead = ((pqc_val / classical_val) - 1) * 100
            print(
                f"| {label} | {int(pqc_val)} bytes | "
                f"{int(classical_val)} bytes | {overhead:+.1f}% |"
            )
    
    if (
        "pqc_query_delegation" in summary
        or "classical_query_delegation" in summary
    ):
        print("\n### System Throughput\n")
        print("| System | Queries/Second |")
        print("|--------|----------------|")

    if "pqc_query_delegation" in summary:
        pqc_throughput = 1000 / summary["pqc_query_delegation"]["mean_ms"]
        print(f"| PQC | {pqc_throughput:.2f} |")
    
    if "classical_query_delegation" in summary:
        classical_throughput = 1000 / summary["classical_query_delegation"]["mean_ms"]
        print(f"| Classical | {classical_throughput:.2f} |")
    
    if (
        "pqc_query_delegation" in summary
        or "classical_query_delegation" in summary
    ):
        print()


def generate_scalability_analysis(data: dict):
    """Generate scalability analysis section."""
    if not data:
        return
    
    pqc_results = data["pqc_results"]
    classical_results = data["classical_results"]
    
    print("\n## Scalability Analysis: Fan-Out Performance\n")
    print("### Total Processing Time\n")
    print("| Workers | PQC Time (ms) | Classical Time (ms) | Overhead |")
    print("|---------|---------------|---------------------|----------|")
    
    for pqc, classical in zip(pqc_results, classical_results):
        overhead = ((pqc["mean_time_ms"] / classical["mean_time_ms"]) - 1) * 100
        print(
            f"| {pqc['num_workers']:7d} | "
            f"{pqc['mean_time_ms']:13.2f} | "
            f"{classical['mean_time_ms']:19.2f} | "
            f"{overhead:+7.1f}% |"
        )
    
    print("\n### System Throughput\n")
    print("| Workers | PQC (req/s) | Classical (req/s) | Ratio |")
    print("|---------|-------------|-------------------|-------|")
    
    for pqc, classical in zip(pqc_results, classical_results):
        pqc_throughput = (pqc["num_workers"] * 1000) / pqc["mean_time_ms"]
        classical_throughput = (classical["num_workers"] * 1000) / classical["mean_time_ms"]
        ratio = classical_throughput / pqc_throughput
        print(f"| {pqc['num_workers']:7d} | {pqc_throughput:11.2f} | {classical_throughput:17.2f} | {ratio:5.2f}x |")
    
    print("\n### Scaling Efficiency (Time per Worker)\n")
    print("| Workers | PQC (ms/worker) | Classical (ms/worker) |")
    print("|---------|-----------------|------------------------|")
    
    for pqc, classical in zip(pqc_results, classical_results):
        pqc_per = pqc["mean_time_ms"] / pqc["num_workers"]
        classical_per = classical["mean_time_ms"] / classical["num_workers"]
        print(f"| {pqc['num_workers']:7d} | {pqc_per:15.2f} | {classical_per:22.2f} |")
    
    print("\n### Key Scalability Findings\n")
    
    if len(pqc_results) >= 2:
        pqc_1 = next(r for r in pqc_results if r["num_workers"] == 1)
        pqc_50 = next((r for r in pqc_results if r["num_workers"] == 50), pqc_results[-1])
        classical_1 = next(r for r in classical_results if r["num_workers"] == 1)
        classical_50 = next((r for r in classical_results if r["num_workers"] == 50), classical_results[-1])
        
        pqc_scale = pqc_50["mean_time_ms"] / pqc_1["mean_time_ms"]
        classical_scale = classical_50["mean_time_ms"] / classical_1["mean_time_ms"]
        
        print(f"- PQC system scales {pqc_scale:.2f}x from 1 to {pqc_50['num_workers']} workers")
        print(f"- Classical system scales {classical_scale:.2f}x from 1 to {classical_50['num_workers']} workers")
        print(f"- PQC maintains {'sub-linear' if pqc_scale < pqc_50['num_workers'] else 'linear'} scaling")
        print(f"- Classical maintains {'sub-linear' if classical_scale < classical_50['num_workers'] else 'linear'} scaling")
    
    print("\n**Plots Available:**")
    print("- `plot_total_time.png`: Total processing time vs workers")
    print("- `plot_throughput.png`: System throughput vs workers")
    print("- `plot_overhead.png`: PQC overhead percentage vs workers")
    print("- `plot_time_per_worker.png`: Scaling efficiency")
    print("- `plot_combined.png`: All metrics in one figure")
    print()


def generate_security_analysis(data: dict):
    """Generate security analysis section."""
    if not data:
        return
    
    print("\n## Security Resilience Analysis\n")
    print("### Attack Simulation Results\n")
    print("| Metric | Count | Rate |")
    print("|--------|-------|------|")
    print(f"| Total Transactions | {data['total_transactions']} | 100.0% |")
    print(f"| Legitimate Transactions | {data['legitimate_transactions']} | {data['legitimate_transactions']/data['total_transactions']*100:.1f}% |")
    print(f"| Attacks Injected | {data['attacks_injected']} | {data['attacks_injected']/data['total_transactions']*100:.1f}% |")
    print(f"| - Tampered Payloads | {data['tampered_injected']} | {data['tampered_injected']/data['total_transactions']*100:.1f}% |")
    print(f"| - Replay Attacks | {data['replay_injected']} | {data['replay_injected']/data['total_transactions']*100:.1f}% |")
    
    print("\n### Detection Performance\n")
    print("| Attack Type | Injected | Detected | Detection Rate |")
    print("|-------------|----------|----------|----------------|")
    
    tamper_rate = data['tampered_detected']/data['tampered_injected']*100 if data['tampered_injected'] > 0 else 0
    replay_rate = data['replay_detected']/data['replay_injected']*100 if data['replay_injected'] > 0 else 0
    
    print(f"| Tampered Payload | {data['tampered_injected']} | {data['tampered_detected']} | {tamper_rate:.1f}% |")
    print(f"| Replay Attack | {data['replay_injected']} | {data['replay_detected']} | {replay_rate:.1f}% |")
    print(f"| **Total** | **{data['attacks_injected']}** | **{data['attacks_detected']}** | **{data['detection_rate']:.1f}%** |")
    
    print("\n### Legitimate Transaction Performance\n")
    print("| Metric | Count | Rate |")
    print("|--------|-------|------|")
    print(f"| Successful | {data['legitimate_success']} | {data['legitimate_success_rate']:.1f}% |")
    print(f"| Failed | {data['legitimate_failed']} | {(data['legitimate_failed']/data['legitimate_transactions']*100) if data['legitimate_transactions'] > 0 else 0:.1f}% |")
    print(f"| False Positives | {data['false_positives']} | {(data['false_positives']/data['legitimate_transactions']*100) if data['legitimate_transactions'] > 0 else 0:.1f}% |")
    
    print("\n### Security Assessment\n")
    
    if data['detection_rate'] == 100.0:
        print("- ✓ **PASS**: 100% attack detection rate achieved")
    else:
        print(f"- ✗ **FAIL**: {100 - data['detection_rate']:.2f}% of attacks were not detected")
    
    if data['false_positives'] == 0:
        print("- ✓ **PASS**: No false positives detected")
    else:
        print(f"- ✗ **WARNING**: {data['false_positives']} false positives detected")
    
    print("\n### Key Security Findings\n")
    print(f"1. System processed {data['total_transactions']} transactions with {data['attacks_injected']} injected attacks")
    print(f"2. Attack detection rate: {data['detection_rate']:.1f}%")
    print(f"3. Tampered payload detection: {tamper_rate:.1f}%")
    print(f"4. Replay attack detection: {replay_rate:.1f}%")
    print(f"5. Legitimate transaction success rate: {data['legitimate_success_rate']:.1f}%")
    print()


def main():
    """Generate all paper results."""
    try:
        data = load_results()
    except FileNotFoundError:
        print("Error: results/benchmark_results.json not found. Run benchmark_pqc.py first.")
        sys.exit(1)
    
    comparative_data = load_comparative_results()
    scalability_data = load_scalability_results()
    security_data = load_security_results()
    
    print("="*60)
    print("PAPER RESULTS GENERATION")
    print("="*60)
    
    generate_key_findings(data)
    generate_markdown_table(data)
    generate_latex_table(data)
    
    if comparative_data:
        generate_comparative_analysis(comparative_data)
    
    if scalability_data:
        generate_scalability_analysis(scalability_data)
    
    if security_data:
        generate_security_analysis(security_data)
    
    # Save to file
    output_file = result_path("paper_results.txt")
    with output_file.open("w") as f:
        old_stdout = sys.stdout
        sys.stdout = f
        generate_key_findings(data)
        generate_markdown_table(data)
        generate_latex_table(data)
        if comparative_data:
            generate_comparative_analysis(comparative_data)
        if scalability_data:
            generate_scalability_analysis(scalability_data)
        if security_data:
            generate_security_analysis(security_data)
        sys.stdout = old_stdout
    
    print("\n" + "="*60)
    print(f"Results saved to: {output_file}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
