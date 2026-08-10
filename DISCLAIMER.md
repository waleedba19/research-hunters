# Disclaimer

## Sci-Hub / Shadow Libraries

This repository includes code that **can** search and download papers from
shadow libraries (Sci-Hub, LibGen, Anna's Archive, Z-Library). These features
are **disabled by default** and must be explicitly enabled.

### How they are gated

- `download_with_full_chain(..., use_scihub=False)` — the default is `False`.
  Callers must pass `use_scihub=True` to enable shadow-library downloads.
- In CI (`research.yml`), the `scihub` workflow input must be set to a
  truthy value (`true` / `yes` / `1`). The default is empty/off.
- In the local interactive prompt, the user is explicitly asked
  ("⚠ Enable Sci-Hub / shadow libraries? (y/n)") and the default is `n`.
- In `platform_registry.py`, shadow libraries are Tier 4 (fallback) and are
  only searched when tier 4 is explicitly requested.

### Legal and ethical considerations

Downloading copyrighted academic papers from shadow libraries may violate
copyright law in your jurisdiction and the terms of service of publishers.
This code is provided for research and educational purposes only. The
maintainers of this repository do not endorse or encourage copyright
infringement.

**You are responsible for compliance with all applicable laws and institutional
policies.** If in doubt, use only the open-access download layers (Unpaywall,
OpenAccess Button, OA.mg, publisher OA pages) which are enabled by default.

### Recommended alternatives

The default download chain (with `use_scihub=False`) already covers:
- Unpaywall API
- OpenAccess Button API
- OA.mg API
- Publisher open-access pages
- Institutional repositories (Zenodo, Figshare, Dryad, OSF)
- Preprint servers (arXiv, bioRxiv, medRxiv, SSRN)

These legal sources successfully retrieve the majority of open-access papers.
