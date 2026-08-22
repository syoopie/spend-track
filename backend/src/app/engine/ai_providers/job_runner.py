"""Shared "run the AI categorization pass in the background" sequence used
by both routers/statements.py (staging) and routers/transactions.py
(recategorize). The two call sites differ only in which in-memory store
they touch and how a suggestion gets applied to a row - the health-check ->
categorize -> re-apply sequence, including the batch-discarded/committed
race guard, lives here once instead of being duplicated per router.
"""

from typing import Callable, TypeVar

from app.engine.ai_providers.base import (
    AiCandidate,
    AiProviderResponseError,
    AiProviderUnavailableError,
    AiSuggestion,
)

BatchT = TypeVar("BatchT")


def run_categorization_job(
    batch_id: str,
    get_batch: Callable[[str], "BatchT | None"],
    apply_suggestions: Callable[["BatchT", list[AiSuggestion]], None],
    candidates: list[AiCandidate],
    categories: list[tuple[str, str]],
    ai_settings: dict,
    fallback_description: str,
) -> None:
    """get_batch(batch_id) resolves the live, mutable batch object, or None
    if it's already been committed/discarded/superseded - called both
    before and after the (possibly long) provider call, since either race
    can happen while the model is thinking. apply_suggestions mutates the
    batch's rows in place and is expected to skip any row the user already
    resolved manually in the meantime (see StagingRow/RecategorizeRow's
    manually_edited field) so a slow AI response can't clobber a decision
    the user already made while it was still in flight."""
    from app.engine.ai_providers import build_provider

    batch = get_batch(batch_id)
    if batch is None:
        return

    provider = build_provider(ai_settings)
    health = provider.check_health()
    if not health.reachable:
        batch.ai_warning = (
            f"AI is enabled but the model can't be reached ({ai_settings['ai_provider']}: {health.error}) - "
            f"{fallback_description}."
        )
        batch.ai_status = "failed"
        return

    try:
        suggestions = provider.categorize(candidates, categories, cancel_key=batch_id)
    except (AiProviderUnavailableError, AiProviderResponseError) as exc:
        batch.ai_warning = (
            f"AI is enabled but the request failed ({ai_settings['ai_provider']}: {exc}) - {fallback_description}."
        )
        batch.ai_status = "failed"
        return

    batch = get_batch(batch_id)  # re-check: may have been committed/discarded while the model was thinking
    if batch is None:
        return

    apply_suggestions(batch, suggestions)
    batch.ai_status = "done"
