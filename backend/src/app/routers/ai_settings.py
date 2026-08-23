"""AI provider configuration: validates and redacts the Ollama /
OpenAI-compatible / Anthropic provider settings. Its own top-level
`/api/ai` prefix (rather than nested under `/api/settings/*`) reflects the
module boundary in the route surface, not just the file layout.
`redact_ai_settings` is exported for routers/settings.py's overview endpoint
to reuse.
"""

from fastapi import APIRouter

from app.config import get_ai_settings, set_ai_settings
from app.engine.ai_providers import build_provider
from app.errors import api_error
from app.models import AiSettingsOut, AiSettingsUpdateRequest, AiStatusOut

router = APIRouter(prefix="/api/ai", tags=["ai"])

_PROVIDER_REQUIREMENTS = {
    "ollama": ("ollama_model", "A model name"),
    "openai_compatible": ("openai_model", "A model name"),
    "anthropic": ("anthropic_model", "A model name"),
}
_PROVIDER_KEY_REQUIREMENTS = {
    "openai_compatible": "openai_api_key",
    "anthropic": "anthropic_api_key",
}


def redact_ai_settings(ai: dict) -> dict:
    def last4(key: str) -> str | None:
        return key[-4:] if len(key) >= 4 else (key or None)

    return {
        "ai_enabled": ai["ai_enabled"],
        "ai_provider": ai["ai_provider"],
        "ollama_url": ai["ollama_url"],
        "ollama_model": ai["ollama_model"],
        "openai_base_url": ai["openai_base_url"],
        "openai_model": ai["openai_model"],
        "openai_api_key_set": bool(ai["openai_api_key"]),
        "openai_api_key_last4": last4(ai["openai_api_key"]) if ai["openai_api_key"] else None,
        "anthropic_model": ai["anthropic_model"],
        "anthropic_api_key_set": bool(ai["anthropic_api_key"]),
        "anthropic_api_key_last4": last4(ai["anthropic_api_key"]) if ai["anthropic_api_key"] else None,
    }


@router.get("/status", response_model=AiStatusOut)
def get_ai_status():
    try:
        provider = build_provider(get_ai_settings())
    except ValueError as exc:
        # Defensive: AiSettingsUpdateRequest.ai_provider is now a Literal, so
        # this can no longer be reached through the API - but a pre-existing
        # or hand-edited config.json could still hold a stale/invalid value,
        # and that should surface as "unreachable", not a 500.
        return AiStatusOut(reachable=False, models=[], error=str(exc))
    health = provider.check_health()
    return AiStatusOut(reachable=health.reachable, models=health.models, error=health.error)


@router.patch("", response_model=AiSettingsOut)
def update_ai_settings(body: AiSettingsUpdateRequest):
    current = get_ai_settings()
    updates = body.model_dump(exclude={"clear_openai_api_key", "clear_anthropic_api_key"}, exclude_none=True)
    # A blank key means "the user didn't type a new one" (the raw key is
    # never echoed back to the frontend, so its input starts empty) - not
    # "clear it". Clearing is only ever the explicit clear_*_api_key flag.
    for key_field in ("openai_api_key", "anthropic_api_key"):
        if not updates.get(key_field):
            updates.pop(key_field, None)
    if body.clear_openai_api_key:
        updates["openai_api_key"] = ""
    if body.clear_anthropic_api_key:
        updates["anthropic_api_key"] = ""

    resulting_provider = updates.get("ai_provider", current["ai_provider"])
    resulting_enabled = updates.get("ai_enabled", current["ai_enabled"])
    if resulting_enabled:
        merged = {**current, **updates}
        # ai_provider on the request is now a Literal, so this can only be
        # reached via a stale/hand-edited config.json still holding an old
        # invalid value - a clean 400 beats a KeyError -> 500.
        requirement = _PROVIDER_REQUIREMENTS.get(resulting_provider)
        if requirement is None:
            raise api_error(
                400, "AI_PROVIDER_NOT_CONFIGURED", f"Unknown AI provider {resulting_provider!r} - re-select a provider."
            )
        model_field, model_label = requirement
        if not merged.get(model_field):
            raise api_error(400, "AI_PROVIDER_NOT_CONFIGURED", f"{model_label} is required for {resulting_provider}.")
        key_field = _PROVIDER_KEY_REQUIREMENTS.get(resulting_provider)
        if key_field and not merged.get(key_field):
            raise api_error(400, "AI_PROVIDER_NOT_CONFIGURED", f"An API key is required for {resulting_provider}.")

    updated = set_ai_settings(**updates)
    return AiSettingsOut(**redact_ai_settings(updated))
