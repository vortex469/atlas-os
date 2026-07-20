from __future__ import annotations

from app.deploy.plan import DeploymentPlan
from app.deploy.recognition.models import (
    ApplicationRecognition,
)


class ApplicationRecognizer:
    """Identify known applications in deployment plans."""

    def recognize(
        self,
        plan: DeploymentPlan,
    ) -> ApplicationRecognition:
        for component in plan.components:
            normalized_image = self._normalize_image(
                component.image
            )

            if self._is_nginx(normalized_image):
                return ApplicationRecognition(
                    application_id="nginx",
                    name="NGINX",
                    category="Web Server / Reverse Proxy",
                    confidence=100,
                    description=(
                        "A high-performance web server "
                        "and reverse proxy."
                    ),
                    matched_component_ids=[
                        component.id
                    ],
                )

        return ApplicationRecognition(
            application_id="unknown",
            name="Unknown Application",
            category="Unknown",
            confidence=0,
            description=(
                "Atlas could not identify a known application "
                "from the deployment components."
            ),
            matched_component_ids=[],
        )

    def _normalize_image(
        self,
        image: str | None,
    ) -> str:
        if image is None:
            return ""

        normalized = image.strip().lower()

        if "@" in normalized:
            normalized = normalized.split("@", 1)[0]

        if ":" in normalized.rsplit("/", 1)[-1]:
            normalized = normalized.rsplit(":", 1)[0]

        return normalized

    def _is_nginx(
        self,
        image: str,
    ) -> bool:
        return image in {
            "nginx",
            "library/nginx",
            "docker.io/library/nginx",
        }