"""
research_hunter_v2_4.py — Shim module that loads `research_hunter_v2-4.py` (dash name)
via importlib and re-exports its full surface as `research_hunter_v2_4`.

The original v2-4 source lives in this repo as `research_hunter_v2-4.py`
(the v6 SUPER LOADED GOD MODE, 283 KB, 70+ search platforms, 14-layer PDF chain).
Because Python module names cannot contain a dash, we use importlib to load it
under the underscore name that v4 expects.

Usage:
    from research_hunter_v2_4 import *   # noqa: F401,F403
    # or:
    import research_hunter_v2_4 as v2_4
"""
import os
import sys
import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_DASH_FILE = os.path.join(_HERE, "research_hunter_v2-4.py")

if not os.path.isfile(_DASH_FILE):
    raise ImportError(
        f"research_hunter_v2-4.py not found at {_DASH_FILE}. "
        "Drop the original v2-4 source file into the repo root."
    )

_spec = importlib.util.spec_from_file_location("_research_hunter_v2_4_dash", _DASH_FILE)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export everything (including underscore-prefixed helpers like _write_master_xlsx)
for _name in dir(_mod):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_mod, _name)

# Make `from research_hunter_v2_4 import X` work for X that exists on the module
sys.modules.setdefault("research_hunter_v2_4", _mod)
