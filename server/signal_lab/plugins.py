"""Discover and load plugins from the plugins directory.

Layout::

    plugins/
      backends/<id>/plugin.yaml   (+ adapter.py, compose.yaml, collector.yaml)
      lessons/<id>/pack.yaml      (+ <lesson>/lesson.md, starter.*, solution.*)
      scenarios/<id>/plugin.yaml  (+ service code)

Nothing in here knows about a specific backend: everything is driven by the
manifests, so adding a plugin never requires touching the core.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .backends import BackendAdapter

log = logging.getLogger("signal_lab.plugins")

FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)
EXT_LANG = {".py": "python", ".metricsql": "metricsql", ".promql": "metricsql", ".esql": "esql", ".yaml": "yaml", ".yml": "yaml"}


def resolve_settings(spec: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, s in (spec or {}).items():
        if not isinstance(s, dict):
            out[key] = str(s)
            continue
        out[key] = os.getenv(s["env"], str(s.get("default", ""))) if s.get("env") else str(s.get("default", ""))
    return out


def fmt(template: str, values: dict[str, Any]) -> str:
    """Format ``{placeholders}`` leaving unknown ones intact."""
    return re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), template)


# ---------------------------------------------------------------- backends


@dataclass
class BackendPlugin:
    id: str
    path: Path
    manifest: dict
    settings: dict[str, str]
    enabled: bool
    adapter: BackendAdapter | None = None

    @property
    def title(self) -> str:
        return self.manifest.get("title", self.id)

    def links(self) -> list[dict]:
        out = []
        for link in self.manifest.get("links", []):
            if "{" in fmt(link["url"], self.settings):  # needs runtime values (e.g. trace_id)
                continue
            out.append({"id": link["id"], "label": link["label"], "url": fmt(link["url"], self.settings), "description": link.get("description", "")})
        return out

    def link_templates(self) -> dict[str, str]:
        return {l["id"]: fmt(l["url"], self.settings) for l in self.manifest.get("links", [])}

    def public(self) -> dict:
        m = self.manifest
        return {
            "id": self.id,
            "title": self.title,
            "description": m.get("description", ""),
            "vendor": m.get("vendor", ""),
            "capabilities": m.get("capabilities", []),
            "query_languages": m.get("query_languages", []),
            "components": m.get("components", []),
            "enabled": self.enabled,
            "links": self.links(),
            "link_templates": self.link_templates(),
            "color": m.get("color"),
            "settings": {k: v for k, v in self.settings.items() if not _is_secret(m, k)},
        }


def _is_secret(manifest: dict, key: str) -> bool:
    spec = (manifest.get("settings") or {}).get(key)
    return isinstance(spec, dict) and bool(spec.get("secret"))


def _load_adapter(plugin: BackendPlugin) -> BackendAdapter | None:
    path = plugin.path / "adapter.py"
    if not path.exists():
        return BackendAdapter(plugin.id, plugin.manifest, plugin.settings)
    mod_name = f"signal_lab_plugin_{plugin.id.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    cls = getattr(module, "Adapter", None)
    if cls is None:
        log.warning("backend %s: adapter.py has no Adapter class", plugin.id)
        return BackendAdapter(plugin.id, plugin.manifest, plugin.settings)
    return cls(plugin.id, plugin.manifest, plugin.settings)


# ---------------------------------------------------------------- lessons


@dataclass
class Lesson:
    id: str  # "<pack>/<slug>"
    pack: str
    slug: str
    module: str
    meta: dict
    body: str
    files: dict[str, dict] = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return self.meta.get("kind", "code")

    def outline(self) -> dict:
        m = self.meta
        return {
            "id": self.id,
            "slug": self.slug,
            "title": m.get("title", self.slug),
            "summary": m.get("summary", ""),
            "kind": self.kind,
            "minutes": m.get("minutes", 5),
            "requires": m.get("requires", []),
            "concepts": m.get("concepts", []),
            # What the lesson assumes you already know, so you can decide to skip it.
            "assumes": m.get("assumes", []),
        }

    def public(self) -> dict:
        m = self.meta
        quiz = m.get("quiz")
        if quiz:  # never leak answers to the client
            quiz = {
                "questions": [
                    {k: v for k, v in q.items() if k not in ("answer", "explanation", "reference", "tolerance_s", "expect", "must_include", "must_match", "mistakes", "alternatives", "hint")} | {"id": q.get("id", f"q{i}")}
                    for i, q in enumerate(quiz.get("questions", []))
                ]
            }
        return self.outline() | {
            "module": self.module,
            "pack": self.pack,
            "body": self.body,
            "checks": [{"id": c["id"], "title": c.get("title", c["id"]), "type": c["type"]} for c in self.checks()],
            "hints": m.get("hints", []),
            "starter": self.files.get("starter"),
            "solution": self.files.get("solution"),
            "traffic": self.files.get("traffic"),
            # The solution needs a value only a live run can give (e.g. a trace id).
            "manual_solution": bool(m.get("manual_solution")),
            "query": m.get("query"),
            "quiz": quiz,
            "tools": m.get("tools", []),
            "scenario": m.get("scenario"),
            "runtime": {k: v for k, v in (m.get("runtime") or {}).items() if k in ("service", "auto_instrument", "timeout")},
            # What learners may see of an experiment or incident (never the incident's timeline).
            "experiment": {k: v for k, v in (m.get("experiment") or {}).items() if k != "inject"} or None,
            "incident": {k: v for k, v in (m.get("incident") or {}).items() if k in ("duration_s", "metrics_only", "brief")} or None,
        }

    def checks(self) -> list[dict]:
        out = []
        for i, c in enumerate(self.meta.get("checks", [])):
            out.append({"id": c.get("id", f"check-{i + 1}")} | c)
        return out


@dataclass
class LessonPack:
    id: str
    path: Path
    manifest: dict
    modules: list[dict]
    lessons: dict[str, Lesson]

    def outline(self, enabled_backends: set[str], capabilities: set[str]) -> dict:
        m = self.manifest
        requires = m.get("requires", {})
        missing_backends = [b for b in requires.get("backends", []) if b not in enabled_backends]
        missing_caps = [c for c in requires.get("capabilities", []) if c not in capabilities]
        return {
            "id": self.id,
            "title": m.get("title", self.id),
            "description": m.get("description", ""),
            "order": m.get("order", 100),
            "icon": m.get("icon"),
            "requires": requires,
            "locked": bool(missing_backends or missing_caps),
            "missing": {"backends": missing_backends, "capabilities": missing_caps},
            "modules": [
                {
                    "id": mod["id"],
                    "title": mod.get("title", mod["id"]),
                    "description": mod.get("description", ""),
                    "assumes": mod.get("assumes", []),
                    "lessons": [self.lessons[f"{self.id}/{slug}"].outline() for slug in mod.get("lessons", []) if f"{self.id}/{slug}" in self.lessons],
                }
                for mod in self.modules
            ],
        }


def _normalise_quiz(meta: dict) -> None:
    """YAML 1.1 reads unquoted yes/no/on/off as booleans: `{id: no}` becomes False,
    and the browser's answer "no" never matches. Option ids and answers are text."""
    def text(v: object) -> object:
        return {True: "yes", False: "no"}.get(v, v) if isinstance(v, bool) else v
    for q in (meta.get("quiz") or {}).get("questions", []):
        for o in q.get("options") or []:
            if isinstance(o, dict) and "id" in o:
                o["id"] = str(text(o["id"]))
        if "answer" in q:
            q["answer"] = [str(text(a)) for a in q["answer"]] if isinstance(q["answer"], list) else text(q["answer"])


def _read_lesson(pack_id: str, module: str, path: Path) -> Lesson | None:
    md = path / "lesson.md"
    if not md.exists():
        log.warning("lesson %s has no lesson.md", path)
        return None
    raw = md.read_text()
    match = FRONT_MATTER.match(raw)
    meta, body = (yaml.safe_load(match.group(1)) or {}, match.group(2)) if match else ({}, raw)
    _normalise_quiz(meta)
    files: dict[str, dict] = {}
    for f in sorted(path.iterdir()):
        stem = f.stem
        if stem in ("starter", "solution") and f.is_file():
            files[stem] = {"filename": meta.get("filename", "main.py" if f.suffix == ".py" else f.name.replace(stem, "query")), "language": EXT_LANG.get(f.suffix, "text"), "content": f.read_text()}
        elif stem == "traffic" and f.is_file():  # read-only program a collector lesson sends through your config
            files["traffic"] = {"filename": f.name, "language": EXT_LANG.get(f.suffix, "text"), "content": f.read_text()}
    return Lesson(id=f"{pack_id}/{path.name}", pack=pack_id, slug=path.name, module=module, meta=meta, body=body.strip(), files=files)


def _load_pack(path: Path) -> LessonPack:
    manifest = yaml.safe_load((path / "pack.yaml").read_text()) or {}
    pack_id = manifest.get("id", path.name)
    lessons: dict[str, Lesson] = {}
    modules = manifest.get("modules", [])
    for mod in modules:
        for slug in mod.get("lessons", []):
            lp = path / slug
            if not lp.is_dir():
                log.warning("pack %s: missing lesson directory %s", pack_id, slug)
                continue
            lesson = _read_lesson(pack_id, mod["id"], lp)
            if lesson:
                lessons[lesson.id] = lesson
    return LessonPack(id=pack_id, path=path, manifest=manifest, modules=modules, lessons=lessons)


# ---------------------------------------------------------------- scenarios


@dataclass
class ScenarioPlugin:
    id: str
    path: Path
    manifest: dict
    settings: dict[str, str]

    def services(self) -> list[dict]:
        out = []
        for svc in self.manifest.get("services", []):
            out.append(
                {
                    "id": svc["id"],
                    "title": svc.get("title", svc["id"]),
                    "description": svc.get("description", ""),
                    "url": fmt(svc["url"], self.settings),
                    "calls": svc.get("calls", []),
                    "role": svc.get("role", "service"),
                }
            )
        return out

    def runner_env(self) -> dict[str, str]:
        return {k: fmt(str(v), self.settings) for k, v in (self.manifest.get("runner_env") or {}).items()}

    def public(self) -> dict:
        return {
            "id": self.id,
            "title": self.manifest.get("title", self.id),
            "description": self.manifest.get("description", ""),
            "services": [{k: v for k, v in s.items() if k != "url"} for s in self.services()],
            "runner_env": list(self.runner_env().keys()),
        }


# ---------------------------------------------------------------- registry


@dataclass
class Registry:
    root: Path
    backends: dict[str, BackendPlugin] = field(default_factory=dict)
    packs: dict[str, LessonPack] = field(default_factory=dict)
    scenarios: dict[str, ScenarioPlugin] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, root: Path, enabled_backends: list[str], enabled_packs: list[str], enabled_scenarios: list[str]) -> "Registry":
        reg = cls(root=root)
        for p in sorted((root / "backends").glob("*/plugin.yaml")):
            try:
                manifest = yaml.safe_load(p.read_text()) or {}
                bid = manifest.get("id", p.parent.name)
                plugin = BackendPlugin(bid, p.parent, manifest, resolve_settings(manifest.get("settings")), bid in enabled_backends)
                if plugin.enabled:
                    plugin.adapter = _load_adapter(plugin)
                reg.backends[bid] = plugin
            except Exception as e:  # a broken plugin must not take the lab down
                reg.errors.append(f"backend {p.parent.name}: {e}")
                log.exception("failed to load backend plugin %s", p)
        for p in sorted((root / "lessons").glob("*/pack.yaml")):
            try:
                pack = _load_pack(p.parent)
                if not enabled_packs or pack.id in enabled_packs:
                    reg.packs[pack.id] = pack
            except Exception as e:
                reg.errors.append(f"lesson pack {p.parent.name}: {e}")
                log.exception("failed to load lesson pack %s", p)
        for p in sorted((root / "scenarios").glob("*/plugin.yaml")):
            try:
                manifest = yaml.safe_load(p.read_text()) or {}
                sid = manifest.get("id", p.parent.name)
                if not enabled_scenarios or sid in enabled_scenarios:
                    reg.scenarios[sid] = ScenarioPlugin(sid, p.parent, manifest, resolve_settings(manifest.get("settings")))
            except Exception as e:
                reg.errors.append(f"scenario {p.parent.name}: {e}")
                log.exception("failed to load scenario %s", p)
        return reg

    def lessons_mtime(self) -> float:
        return max((f.stat().st_mtime for f in (self.root / "lessons").rglob("*") if f.is_file()), default=0.0)

    def reload_packs(self, enabled_packs: list[str]) -> None:
        packs: dict[str, LessonPack] = {}
        for p in sorted((self.root / "lessons").glob("*/pack.yaml")):
            try:
                pack = _load_pack(p.parent)
                if not enabled_packs or pack.id in enabled_packs:
                    packs[pack.id] = pack
            except Exception as e:
                log.error("reload failed for %s: %s", p, e)
                return
        self.packs = packs

    @property
    def enabled_backends(self) -> list[BackendPlugin]:
        return [b for b in self.backends.values() if b.enabled]

    def capabilities(self) -> set[str]:
        caps: set[str] = set()
        for b in self.enabled_backends:
            caps.update(b.manifest.get("capabilities", []))
        return caps

    def lesson(self, lesson_id: str) -> Lesson | None:
        pack_id = lesson_id.split("/", 1)[0]
        pack = self.packs.get(pack_id)
        return pack.lessons.get(lesson_id) if pack else None

    def course(self) -> list[dict]:
        enabled = {b.id for b in self.enabled_backends}
        caps = self.capabilities()
        return sorted((p.outline(enabled, caps) for p in self.packs.values()), key=lambda p: (p["order"], p["title"]))

    def scenario(self) -> ScenarioPlugin | None:
        return next(iter(self.scenarios.values()), None)
