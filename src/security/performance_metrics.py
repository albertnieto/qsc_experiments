# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Performance metrics collection for PQC operations."""
import time
import logging
from typing import Dict, Any, List
from dataclasses import dataclass, asdict
import json
import math
import statistics
from .benchmark_metadata import run_metadata

logger = logging.getLogger(__name__)


@dataclass
class MetricResult:
    """Single metric measurement."""
    operation: str
    duration_ms: float
    size_bytes: int = 0
    metadata: Dict[str, Any] = None


class PerformanceMetrics:
    """Collects and reports performance metrics for PQC operations."""

    def __init__(self):
        self.metrics: List[MetricResult] = []

    def measure(self, operation: str, size_bytes: int = 0, **metadata):
        """Context manager for measuring operation time."""
        return MetricContext(self, operation, size_bytes, metadata)

    def add_metric(self, metric: MetricResult):
        """Add a metric result."""
        self.metrics.append(metric)
        logger.debug(f"Metric: {metric.operation} = {metric.duration_ms:.2f}ms")

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if not self.metrics:
            return {}

        by_operation = {}
        for metric in self.metrics:
            if metric.operation not in by_operation:
                by_operation[metric.operation] = {"times": [], "sizes": []}
            by_operation[metric.operation]["times"].append(metric.duration_ms)
            by_operation[metric.operation]["sizes"].append(metric.size_bytes)

        summary = {}
        for op, data in by_operation.items():
            times = data["times"]
            sizes = data["sizes"]
            summary[op] = {
                "count": len(times),
                "mean_ms": sum(times) / len(times),
                "min_ms": min(times),
                "max_ms": max(times),
                "total_ms": sum(times),
                "total_bytes": sum(sizes)
            }
            if len(times) > 1:
                standard_error = statistics.stdev(times) / math.sqrt(len(times))
                summary[op]["stdev_ms"] = statistics.stdev(times)
                summary[op]["ci95_ms"] = 1.96 * standard_error
            else:
                summary[op]["stdev_ms"] = 0.0
                summary[op]["ci95_ms"] = 0.0

        return summary

    def export_json(self, filepath: str):
        """Export metrics to JSON file."""
        data = {
            "measurement_type": "mixed",
            "measurement_types": {
                "pqc_and_classical_crypto": "M-local",
                "qrng_provider": "S-simulation unless a hardware provider is configured",
                "qkd_provider": "Model-QKD",
            },
            "provenance": "benchmark metric collection; inspect metric names for scope",
            "run_metadata": run_metadata(repetitions=len(self.metrics)),
            "summary": self.get_summary(),
            "raw_metrics": [asdict(m) for m in self.metrics]
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Metrics exported to {filepath}")

    def print_summary(self):
        """Print summary to console."""
        summary = self.get_summary()
        print("\n" + "="*60)
        print("PERFORMANCE METRICS SUMMARY")
        print("="*60)
        for op, stats in summary.items():
            print(f"\n{op}:")
            print(f"  Count: {stats['count']}")
            print(f"  Mean:  {stats['mean_ms']:.2f} ms")
            print(f"  Min:   {stats['min_ms']:.2f} ms")
            print(f"  Max:   {stats['max_ms']:.2f} ms")
        print("="*60 + "\n")


class MetricContext:
    """Context manager for timing operations."""

    def __init__(self, metrics: PerformanceMetrics, operation: str, size_bytes: int, metadata: Dict):
        self.metrics = metrics
        self.operation = operation
        self.size_bytes = size_bytes
        self.metadata = metadata or {}
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        metric = MetricResult(
            operation=self.operation,
            duration_ms=duration_ms,
            size_bytes=self.size_bytes,
            metadata=self.metadata
        )
        self.metrics.add_metric(metric)
