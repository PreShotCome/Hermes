"""GPU power/utilization sampling via nvidia-smi, for efficiency telemetry.

Returns the current board power draw (watts), GPU utilization (%) and
temperature (°C). On machines without an NVIDIA GPU (or without nvidia-smi) it
returns ``None`` and the worker simply reports zeros — reference/CPU runs still
work, they just have no GPU power to show.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class PowerSample:
    power_watts: float
    gpu_util: float
    gpu_temp: float


_QUERY = "power.draw,utilization.gpu,temperature.gpu"


def sample_gpu(gpu_index: int = 0) -> PowerSample | None:
    """Sample the given GPU's power/util/temp, or None if unavailable."""
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                f"--query-gpu={_QUERY}",
                "--format=csv,noheader,nounits",
                f"--id={gpu_index}",
            ],
            text=True,
            timeout=3,
        )
    except Exception:
        return None
    line = out.strip().splitlines()
    if not line:
        return None
    parts = [p.strip() for p in line[0].split(",")]
    if len(parts) < 3:
        return None
    try:
        return PowerSample(
            power_watts=float(parts[0]),
            gpu_util=float(parts[1]),
            gpu_temp=float(parts[2]),
        )
    except ValueError:
        # Some fields read "[N/A]" on certain cards/driver states.
        return None
