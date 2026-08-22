from app.engine.ai_providers.anthropic import AnthropicProvider
from app.engine.ai_providers.base import (
    AiCandidate,
    AiProvider,
    AiProviderResponseError,
    AiProviderUnavailableError,
    AiSuggestion,
    ProviderHealth,
)
from app.engine.ai_providers.job_runner import run_categorization_job
from app.engine.ai_providers.ollama import OllamaProvider
from app.engine.ai_providers.openai_compatible import OpenAiCompatibleProvider


def build_provider(ai_settings: dict) -> AiProvider:
    provider = ai_settings.get("ai_provider", "ollama")
    if provider == "ollama":
        return OllamaProvider(base_url=ai_settings["ollama_url"], model=ai_settings["ollama_model"])
    if provider == "openai_compatible":
        return OpenAiCompatibleProvider(
            base_url=ai_settings["openai_base_url"],
            api_key=ai_settings["openai_api_key"],
            model=ai_settings["openai_model"],
        )
    if provider == "anthropic":
        return AnthropicProvider(api_key=ai_settings["anthropic_api_key"], model=ai_settings["anthropic_model"])
    raise ValueError(f"Unknown ai_provider: {provider!r}")


def active_model_name(ai_settings: dict) -> str:
    """The configured model name for whichever provider is currently active -
    used to label the "AI is categorizing with {model}" progress banner
    without the caller needing to know the provider's field-naming scheme."""
    provider = ai_settings.get("ai_provider", "ollama")
    if provider == "ollama":
        return ai_settings["ollama_model"]
    if provider == "openai_compatible":
        return ai_settings["openai_model"]
    if provider == "anthropic":
        return ai_settings["anthropic_model"]
    return ""


__all__ = [
    "AiCandidate",
    "AiProvider",
    "AiProviderResponseError",
    "AiProviderUnavailableError",
    "AiSuggestion",
    "ProviderHealth",
    "build_provider",
    "active_model_name",
    "run_categorization_job",
]
