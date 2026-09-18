# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from csfarm.models import AppIdentity, Recipe


@dataclass(frozen=True)
class AppRef:
    type: str
    name: str
    path: Path
    identity: AppIdentity

    @property
    def id(self) -> str:
        return self.identity.id

    def versions_dir(self) -> Path:
        return self.path / "versions"

    def list_versions(self) -> list[str]:
        root = self.versions_dir()
        if not root.is_dir():
            return []
        return sorted(
            (p.name for p in root.iterdir() if p.is_dir() and (p / "recipe.json").is_file()),
            key=str.casefold,
        )

    def load_recipe(self, version: str | None = None) -> tuple[str, Recipe]:
        ver = version or self.identity.default_version
        recipe_path = self.versions_dir() / ver / "recipe.json"
        if not recipe_path.is_file():
            available = ", ".join(self.list_versions()) or "(none)"
            raise FileNotFoundError(
                f"No recipe for {self.id}@{ver} at {recipe_path}; versions: {available}"
            )
        data = json.loads(recipe_path.read_text(encoding="utf-8"))
        return ver, Recipe.model_validate(data)


def _linguistic_dirs(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted((p for p in path.iterdir() if p.is_dir()), key=lambda p: p.name.casefold())


class Catalog:
    """Discover apps under apps/<type>/<name>/ in linguistic (A–Z) order."""

    def __init__(self, apps_root: Path) -> None:
        self.apps_root = apps_root

    def iter_types(self) -> list[str]:
        return [p.name for p in _linguistic_dirs(self.apps_root)]

    def iter_apps(self, type_name: str | None = None) -> list[AppRef]:
        apps: list[AppRef] = []
        types = [type_name] if type_name else self.iter_types()
        for t in types:
            type_dir = self.apps_root / t
            if not type_dir.is_dir():
                continue
            for app_dir in _linguistic_dirs(type_dir):
                app_json = app_dir / "app.json"
                if not app_json.is_file():
                    continue
                identity = AppIdentity.model_validate(json.loads(app_json.read_text(encoding="utf-8")))
                apps.append(AppRef(type=t, name=app_dir.name, path=app_dir, identity=identity))
        # Already walked linguistically; keep stable order
        return apps

    def get(self, app_id: str) -> AppRef:
        """Resolve typed id `type/name` or `type/name@version` (version ignored here)."""
        core = app_id.split("@", 1)[0]
        parts = core.split("/")
        if len(parts) != 2:
            raise ValueError(f"App id must be type/name, got {app_id!r}")
        type_name, name = parts
        app_dir = self.apps_root / type_name / name
        app_json = app_dir / "app.json"
        if not app_json.is_file():
            raise FileNotFoundError(f"Unknown app {app_id!r}; expected {app_json}")
        identity = AppIdentity.model_validate(json.loads(app_json.read_text(encoding="utf-8")))
        return AppRef(type=type_name, name=name, path=app_dir, identity=identity)

    def parse_target(self, target: str) -> tuple[AppRef, str]:
        """Parse `type/name` or `type/name@version` → (app, version)."""
        if "@" in target:
            app_id, version = target.split("@", 1)
        else:
            app_id, version = target, None
        app = self.get(app_id)
        ver = version or app.identity.default_version
        return app, ver
