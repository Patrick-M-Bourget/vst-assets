# Components carry their own shadows

Each Frame renders its Component's shadow onto an invisible shadow-catcher floor at the Panel's face, so the shadow arrives in the Frame's alpha and moves with the part: a Knob's tail as it turns, a Toggle's bat as it flips. A Frame's rectangle grows toward where the key light throws shadows (bottom-right), so its bounds are no longer centred on the Component. The Backplate keeps shadows only for what never moves: plate, ears, screws, hinge, and later the meter bezel.

This replaces ADR 0001's rule that every Component's shadow is baked into the Backplate. A baked shadow can show only one position, and for most Frames it would point the wrong way.

The catcher records anything a Component blocks, so only the key may be blocked. The studio HDRI lights nothing directly (it shows only in reflections), and the even ambient light comes from a fill that no Component blocks (shadow linking; the light's own "no shadow" switch isn't enough for the catcher). Otherwise the catcher records a soft dark halo around every Component, which runs past the Frame's edge and leaves a visible rectangle on the Panel.

## Considered Options

- **Bake the shadow of a round stand-in.** Rejected: the tail and the Toggle's bat would cast no shadow, and look pasted on.
- **Bake a contact shadow and add moving parts' shadows per Frame.** Rejected: the two overlap and darken where they meet.

## Consequences

- Drafts render with Cycles too (fewer samples): Eevee has no shadow catcher.
- `pack.py` warns when a Frame's border isn't transparent: a shadow or part runs off its edge.
- A Component's Frames are larger than the Component, by its shadow's reach.
