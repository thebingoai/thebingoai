"""
agent_profile_renderer.py — Renders AgentProfile structured fields into text columns.

The agent runtime reads identity and user_context as plain text (via ProfileRenderer).
This service auto-generates those text columns from the structured UI fields on each
draft save, so the agent always sees up-to-date content without changes to ProfileRenderer.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.agent_profile import AgentProfile


def _get_default_section(section: str) -> str:
    """Fetch fallback text, returning empty string on import failure."""
    try:
        from backend.agents.profile_defaults import get_default_section
        return get_default_section("orchestrator", section) or ""
    except Exception:
        return ""


def render_identity_text(profile: "AgentProfile") -> str:
    """Produce the identity text column from structured identity fields."""
    name = profile.display_name or "Bingo"
    parts = [f"Your name is {name}."]
    if profile.pronouns:
        parts.append(f"Your pronouns are {profile.pronouns}.")
    if profile.tagline:
        parts.append(f'Your tagline: "{profile.tagline}".')

    header = " ".join(parts)
    base = _get_default_section("identity")
    return f"{header}\n\n{base}".strip()


def render_user_context_text(profile: "AgentProfile") -> str:
    """Produce the user_context text column from structured user context fields."""
    lines: list[str] = []

    up = profile.user_profile or {}
    profile_keys = ("address_as", "pronouns", "role", "team", "timezone", "working_hours")
    if any(up.get(k) for k in profile_keys):
        lines.append("## About This User\n")
        if up.get("address_as"):
            lines.append(f"- **Name:** {up['address_as']}")
        if up.get("pronouns"):
            lines.append(f"- **Pronouns:** {up['pronouns']}")
        if up.get("role"):
            lines.append(f"- **Role:** {up['role']}")
        if up.get("team"):
            lines.append(f"- **Team:** {up['team']}")
        if up.get("timezone"):
            lines.append(f"- **Timezone:** {up['timezone']}")
        if up.get("working_hours"):
            lines.append(f"- **Working hours:** {up['working_hours']}")
        lines.append("")

    if profile.user_narrative:
        lines.append("## Narrative\n")
        lines.append(profile.user_narrative)
        lines.append("")

    vocab = profile.vocabulary or []
    if vocab:
        lines.append("## Vocabulary\n")
        for item in vocab:
            term = item.get('term', '') or ''
            definition = item.get('definition', '') or ''
            lines.append(f"- **{term}**: {definition}")
        lines.append("")

    if profile.sensitivities:
        lines.append("## Sensitivities\n")
        for sensitivity in profile.sensitivities:
            lines.append(f"- {sensitivity}")

    if not lines:
        return _get_default_section("user_context")

    return "\n".join(lines)
