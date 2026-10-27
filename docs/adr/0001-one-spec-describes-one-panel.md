# One Spec describes one Panel

Each Spec is one plugin's whole Panel: a Backplate and the Components placed on it, lit by one light rig and seen by one orthographic camera. Consistent light across every asset is what makes a skeuomorphic Panel read as real, and rendering the Panel as one scene gives it for free, with each Component's contact shadow baked into the Backplate from the same light.

## Considered Options

- **A library of loose Components.** Rejected for v1: with no Backplate under them, each Component must carry its own shadow in its alpha, which looks wrong on a textured panel. A later Spec may set `"backplate": false` for this.

## Consequences

- A Component's Frames hold no shadow on the Panel; the Backplate holds it.
- Moving a Component means a new Render of the Backplate.
