"""Template registry."""

from composer_service.templates.base import Template


class TemplateRegistry:
    """Registry of templates. Templates are registered in main.py."""

    def __init__(self) -> None:
        self._templates: dict[str, Template] = {}

    def register(self, template: Template) -> None:
        key = f"{template.template_id}:{template.template_version}"
        if key in self._templates:
            raise ValueError(f"Template already registered: {key}")
        self._templates[key] = template

    def get(self, template_id: str, template_version: str | None = None) -> Template:
        if template_version is None:
            candidates = [t for t in self._templates.values() if t.template_id == template_id]
            if not candidates:
                raise ValueError(f"Template not found: {template_id}")
            candidates.sort(key=lambda t: t.template_version, reverse=True)
            return candidates[0]
        key = f"{template_id}:{template_version}"
        if key not in self._templates:
            raise ValueError(f"Template not found: {key}")
        return self._templates[key]

    def list_all(self) -> list[dict[str, str]]:
        return [
            {
                "template_id": t.template_id,
                "template_version": t.template_version,
                "channel": t.channel,
            }
            for t in self._templates.values()
        ]

    def default_for_channel(self, channel: str) -> Template:
        for t in self._templates.values():
            if t.channel == channel:
                return t
        raise ValueError(f"No template for channel: {channel}")
