# Refs stay on the user's machine

The repo is public and Refs are usually other people's photographs, so `refs/` is gitignored, and so is everything derived from them (the moodboard and `compare.png`, under `out/`). A Spec keeps the written Look Brief and the Refs' file names in its `notes`, which is enough to trace a look back to its sources on the user's machine.

## Considered Options

- **Committing Refs in a private repo.** Rejected when the repo was made public.

## Consequences

- Committed images are only our own Renders.
- Someone cloning the repo can render every Spec but can't see the Refs behind it.
