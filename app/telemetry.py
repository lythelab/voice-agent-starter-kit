from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean


@dataclass
class MetricSummary:
    count: int
    avg_ms: float
    min_ms: float
    p95_ms: float
    max_ms: float
    last_ms: float


class LatencyStore:
    def __init__(self, max_samples: int = 300) -> None:
        self.max_samples = max_samples
        self._samples: dict[str, list[float]] = defaultdict(list)

    def add(self, metric_name: str, value_ms: float) -> None:
        values = self._samples[metric_name]
        values.append(max(0.0, float(value_ms)))
        if len(values) > self.max_samples:
            del values[:-self.max_samples]

    def _summarize(self, values: list[float]) -> MetricSummary:
        ordered = sorted(values)
        index = int(round(0.95 * (len(ordered) - 1)))
        return MetricSummary(
            count=len(values),
            avg_ms=mean(values),
            min_ms=ordered[0],
            p95_ms=ordered[index],
            max_ms=ordered[-1],
            last_ms=values[-1],
        )

    def summary(self) -> dict[str, dict[str, float | int]]:
        output: dict[str, dict[str, float | int]] = {}
        for metric_name, values in sorted(self._samples.items()):
            if not values:
                continue
            summary = self._summarize(values)
            output[metric_name] = {
                "count": summary.count,
                "avg_ms": round(summary.avg_ms, 2),
                "min_ms": round(summary.min_ms, 2),
                "p95_ms": round(summary.p95_ms, 2),
                "max_ms": round(summary.max_ms, 2),
                "last_ms": round(summary.last_ms, 2),
            }
        return output


latency_store = LatencyStore()
