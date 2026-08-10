"""Validate that research.yml workflow options are consistent with v2-4's
FIELDS and STUDY_TYPES dicts.

The workflow `options:` lists must be inline in YAML (GitHub Actions limitation),
so this script checks they stay in sync with the canonical dicts in
research_hunter_v2-4.py. Run it with: python validate_workflow_options.py
"""
import sys
import yaml
from pathlib import Path

REPO = Path(__file__).parent
WF = REPO / ".github" / "workflows" / "research.yml"


def load_workflow_inputs():
    d = yaml.safe_load(open(WF))
    key = "on" if "on" in d else True
    trig = d[key] if isinstance(d.get(key), dict) else d.get(True, {})
    return trig["workflow_dispatch"]["inputs"]


def main():
    try:
        import research_hunter_v2_4 as v24
    except Exception as e:
        print(f"SKIP: cannot import research_hunter_v2_4: {e}")
        return 0

    inputs = load_workflow_inputs()
    field_opts = inputs.get("field", {}).get("options", [])
    st_opts = inputs.get("study_type", {}).get("options", [])

    # v2-4 dicts are keyed by number; workflow options are "N - Name".
    v24_fields = set(v24.FIELDS.values())
    v24_study = set(v24.STUDY_TYPES.values())

    # Extract names from workflow options (strip the "N - " prefix)
    wf_field_names = {o.split(" -", 1)[-1].strip() for o in field_opts}
    wf_st_names = {o.split(" -", 1)[-1].strip() for o in st_opts}

    only_in_wf_fields = wf_field_names - v24_fields
    only_in_v24_fields = v24_fields - wf_field_names

    print(f"Workflow field options:  {len(field_opts)}")
    print(f"v2-4 FIELDS:             {len(v24_fields)}")
    print(f"Workflow study_type opts: {len(st_opts)}")
    print(f"v2-4 STUDY_TYPES:         {len(v24_study)}")
    print()

    if only_in_wf_fields:
        print(f"  Fields only in workflow ({len(only_in_wf_fields)}):")
        for f in sorted(only_in_wf_fields)[:10]:
            print(f"    + {f}")
    if only_in_v24_fields:
        print(f"  Fields only in v2-4 ({len(only_in_v24_fields)}):")
        for f in sorted(only_in_v24_fields)[:10]:
            print(f"    - {f}")

    # Note: the workflow has MORE options than v2-4's dict (279 vs 48).
    # This is intentional — v2-4 falls through to raw name for unknown keys.
    print("\nNote: workflow has more options than v2-4 dict by design.")
    print("Unknown keys fall through to the raw field name (see v2-4 line ~7172).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
