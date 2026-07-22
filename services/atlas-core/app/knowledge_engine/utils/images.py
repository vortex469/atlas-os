from __future__ import annotations


def normalize_image(image: str) -> str:
    """Normalize a container image name."""

    normalized = (
        image.strip()
        .lower()
        .split("@", 1)[0]
    )

    if ":" in normalized.rsplit("/", 1)[-1]:
        normalized = normalized.rsplit(":", 1)[0]

    return normalized