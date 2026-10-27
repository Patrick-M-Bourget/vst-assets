# One Spec describes one Panel

Each Spec is one plugin's whole Panel: a Backplate and the Components placed on it, lit by one light rig and seen by one orthographic camera. Consistent light across every asset is what makes a skeuomorphic Panel read as real, and rendering the Panel as one scene gives it for free. (Where the Components' shadows go is ADR 0007.)

## Considered Options

- **A library of loose Components.** Rejected for v1: loose Components lose the shared light and placement a Panel gives them. A later Spec may set `"backplate": false` for this.

## Consequences

- Moving a Component means a new Render of the Backplate.
