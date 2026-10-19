from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    path = Path(__file__).resolve().parents[2] / "microdrama-subtitles/scripts/make_subtitles.py"
    name = "_seed_shared_subtitle_engine"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Shared subtitle implementation is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return int(module.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
