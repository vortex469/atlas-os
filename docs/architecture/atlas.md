# Atlas Architecture

The canonical current architecture is maintained in
[../../ARCHITECTURE.md](../../ARCHITECTURE.md). It documents the released Atlas
v0.15.0 production topology, with P0 through P5 complete, at release commit
`850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`; its read-only grounding surface,
overlays, state boundaries, and four distinct mutation/side-effect surfaces.
This pointer is intentional: duplicating the former two-service description
caused release drift.
