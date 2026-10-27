# vst-assets

Generates skeuomorphic UI assets for audio plugins (backplates, filmstrips and overlays for JUCE-style editors) by rendering procedural 3D scenes in headless Blender. One spec describes one panel. The spec is issue #1. Use the vocabulary in `GLOSSARY.md` and respect the decisions in `docs/adr/`.

GitHub account: `Patrick-M-Bourget`. Run `gh auth status` before any `git push`.

## Running

- Blender is pinned to **5.2.3 LTS** (`brew install --cask blender`). Bump it deliberately: re-render a spec and compare before committing.
- Render: `blender -b --factory-startup -P blender/render.py -- specs/<name>.json`, which writes to `out/<name>/`.
- Tests: `python3 -m unittest discover tests`. Run them before every commit.
- Blender's bundled Python has no PIL; anything that needs PIL runs under the system `python3` in `tools/`.

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues for Patrick-M-Bourget/vst-assets, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
