"""
AnomalyDetector — detección de anomalías con ML local (sin LLM).

Mantiene baseline estadístico de:
  - Volumen de mensajes por tipo/flow
  - Tiempos de procesamiento
  - Distribución de tamaños de mensaje
  - Frecuencia de errores

Alerta cuando detecta drift significativo.
No usa Claude — sin latencia de API, sin costo.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class MetricWindow:
    """Ventana de métricas con stats básicos."""

    values: list[float] = field(default_factory=list)
    window_size: int = 1000

    def add(self, value: float) -> None:
        self.values.append(value)
        if len(self.values) > self.window_size:
            self.values = self.values[-self.window_size:]

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def mean(self) -> float:
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)

    @property
    def std_dev(self) -> float:
        if len(self.values) < 2:
            return 0.0
        mean = self.mean
        variance = sum((x - mean) ** 2 for x in self.values) / (len(self.values) - 1)
        return variance ** 0.5

    @property
    def min(self) -> float:
        return min(self.values) if self.values else 0.0

    @property
    def max(self) -> float:
        return max(self.values) if self.values else 0.0


@dataclass
class Anomaly:
    """Una anomalía detectada."""

    metric: str
    current_value: float
    expected_mean: float
    expected_std: float
    deviation: float  # Number of standard deviations
    severity: str  # "warning" or "critical"
    timestamp: float
    description: str


class AnomalyDetector:
    """Detector de anomalías basado en estadísticas locales."""

    def __init__(self, warning_threshold: float = 2.0, critical_threshold: float = 3.0):
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold

        # Métricas por tipo
        self._processing_times: dict[str, MetricWindow] = defaultdict(MetricWindow)
        self._message_sizes: dict[str, MetricWindow] = defaultdict(MetricWindow)
        self._error_rates: dict[str, MetricWindow] = defaultdict(MetricWindow)
        self._message_counts: dict[str, list[float]] = defaultdict(list)

        # Ventana de conteo por minuto
        self._minute_counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

        self._anomalies: list[Anomaly] = []
        self._max_anomalies = 1000

    def record_message(
        self,
        message_type: str,
        flow_id: str,
        processing_time_ms: float,
        raw_size: int,
        is_error: bool = False,
    ) -> list[Anomaly]:
        """Registrar un mensaje procesado y detectar anomalías.

        Returns:
            Lista de anomalías nuevas detectadas.
        """
        new_anomalies = []
        key = f"{flow_id}:{message_type}"
        now = time.time()
        minute = int(now / 60)

        # Record metrics
        self._processing_times[key].add(processing_time_ms)
        self._message_sizes[key].add(float(raw_size))
        self._error_rates[key].add(1.0 if is_error else 0.0)
        self._minute_counts[key][minute] += 1

        # Check processing time anomaly (only after baseline)
        window = self._processing_times[key]
        if window.count > 50:
            anomaly = self._check_anomaly(
                f"processing_time:{key}",
                processing_time_ms,
                window,
                f"Processing time for {message_type} in flow {flow_id}",
            )
            if anomaly:
                new_anomalies.append(anomaly)

        # Check message size anomaly
        size_window = self._message_sizes[key]
        if size_window.count > 50:
            anomaly = self._check_anomaly(
                f"message_size:{key}",
                float(raw_size),
                size_window,
                f"Message size for {message_type} in flow {flow_id}",
            )
            if anomaly:
                new_anomalies.append(anomaly)

        # Check error rate spike
        error_window = self._error_rates[key]
        if error_window.count > 100:
            recent_errors = error_window.values[-20:]
            recent_rate = sum(recent_errors) / len(recent_errors)
            overall_rate = error_window.mean
            if overall_rate > 0 and recent_rate > overall_rate * 3:
                anomaly = Anomaly(
                    metric=f"error_rate:{key}",
                    current_value=recent_rate,
                    expected_mean=overall_rate,
                    expected_std=error_window.std_dev,
                    deviation=(recent_rate - overall_rate) / max(error_window.std_dev, 0.01),
                    severity="critical" if recent_rate > 0.5 else "warning",
                    timestamp=now,
                    description=f"Error rate spike for {message_type}: {recent_rate:.1%} vs baseline {overall_rate:.1%}",
                )
                new_anomalies.append(anomaly)

        # Store anomalies
        for a in new_anomalies:
            self._anomalies.append(a)
            logger.warning(
                "anomaly_detected",
                metric=a.metric,
                severity=a.severity,
                deviation=round(a.deviation, 2),
                description=a.description,
            )

        if len(self._anomalies) > self._max_anomalies:
            self._anomalies = self._anomalies[-self._max_anomalies:]

        return new_anomalies

    def _check_anomaly(
        self,
        metric: str,
        value: float,
        window: MetricWindow,
        description_prefix: str,
    ) -> Optional[Anomaly]:
        """Detectar anomalía basada en desviación estándar."""
        if window.std_dev == 0:
            return None

        deviation = abs(value - window.mean) / window.std_dev

        if deviation >= self._critical_threshold:
            severity = "critical"
        elif deviation >= self._warning_threshold:
            severity = "warning"
        else:
            return None

        return Anomaly(
            metric=metric,
            current_value=value,
            expected_mean=window.mean,
            expected_std=window.std_dev,
            deviation=deviation,
            severity=severity,
            timestamp=time.time(),
            description=f"{description_prefix}: {value:.1f} ({deviation:.1f}σ from mean {window.mean:.1f})",
        )

    def get_recent_anomalies(self, limit: int = 50) -> list[Anomaly]:
        """Obtener anomalías recientes."""
        return self._anomalies[-limit:]

    def get_stats(self) -> dict:
        """Obtener estadísticas actuales."""
        stats = {}
        for key, window in self._processing_times.items():
            if window.count > 0:
                stats[key] = {
                    "count": window.count,
                    "mean_ms": round(window.mean, 2),
                    "std_ms": round(window.std_dev, 2),
                    "min_ms": round(window.min, 2),
                    "max_ms": round(window.max, 2),
                    "error_rate": round(self._error_rates.get(key, MetricWindow()).mean, 4),
                }
        return stats
