from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _list(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


def _collector_paths(raw: str) -> list[str]:
    if "--config" in raw:
        return [tok.split("=", 1)[1] for tok in raw.split() if tok.startswith("--config=")]
    return [x.strip() for x in raw.split(",") if x.strip()]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    port: int = int(os.getenv("SIGNAL_LAB_PORT", "8000"))
    plugins_dir: Path = Path(os.getenv("SIGNAL_LAB_PLUGINS_DIR", str(ROOT / "plugins")))
    static_dir: Path = Path(os.getenv("SIGNAL_LAB_STATIC_DIR", str(ROOT / "web" / "dist")))
    backends: list[str] = field(default_factory=lambda: _list("SIGNAL_LAB_BACKENDS"))
    lesson_packs: list[str] = field(default_factory=lambda: _list("SIGNAL_LAB_LESSON_PACKS"))
    scenarios: list[str] = field(default_factory=lambda: _list("SIGNAL_LAB_SCENARIOS"))
    # Where learner code sends OTLP. In compose/Helm this is the Collector;
    # in dev it defaults to the lab's own tap so nothing else is needed.
    otlp_endpoint: str = os.getenv("SIGNAL_LAB_OTLP_ENDPOINT", "")
    collector_health_url: str = os.getenv("SIGNAL_LAB_COLLECTOR_HEALTH_URL", "")
    # Either a comma list of paths or the collector's own "--config=a --config=b" args.
    collector_configs: list[str] = field(default_factory=lambda: _collector_paths(os.getenv("SIGNAL_LAB_COLLECTOR_CONFIGS", "")))
    runner_url: str = os.getenv("SIGNAL_LAB_RUNNER_URL", "")
    run_timeout: float = float(os.getenv("SIGNAL_LAB_RUN_TIMEOUT", "20"))
    runs_enabled: bool = _bool("SIGNAL_LAB_RUNS_ENABLED", True)
    reload: bool = _bool("SIGNAL_LAB_RELOAD", False)  # re-read lesson packs on change (for authors)
    environment: str = os.getenv("SIGNAL_LAB_ENVIRONMENT", "lab")

    @property
    def effective_otlp_endpoint(self) -> str:
        return self.otlp_endpoint or f"http://127.0.0.1:{self.port}/tap"
