from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable
from urllib.parse import urlsplit

from .messages import _current_branch_nodes, _message_from_node
from .product_observations import _safe_source_url

_PR93_CANONICAL_OBSERVATION_GATE_MARKER = "__pr93_canonical_product_observation_gate__"
_MAX_SOURCES_PER_REFERENCE = 64
_MAX_SOURCES_PER_TURN = 128
_MAX_REFERENCES_PER_MESSAGE = 128
_MAX_TITLE_CHARS = 512
_MAX_ATTRIBUTION_CHARS = 256
_MAX_REFERENCE_TYPE_CHARS = 96


def _optional_text(value: Any, *, max_chars: int | None = None) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.replace("\x00", "").strip()
    if not value:
        return None
    return value[:max_chars] if max_chars is not None else value


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _reference_type(value: Any) -> str | None:
    text = _optional_text(value, max_chars=_MAX_REFERENCE_TYPE_CHARS)
    if text is None:
        return None
    normalized = "".join(
        character if character.isalnum() or character in "_.:-" else "_"
        for character in text.casefold()
    )
    return normalized[:_MAX_REFERENCE_TYPE_CHARS] or None


def _source_candidate(value: Any) -> dict[str, str | None] | None:
    if not isinstance(value, dict):
        return None
    url = _safe_source_url(value.get("url"))
    if url is None:
        return None
    try:
        domain = urlsplit(url).hostname
    except ValueError:
        domain = None
    return {
        "url": url,
        "title": _optional_text(value.get("title"), max_chars=_MAX_TITLE_CHARS),
        "attribution": _optional_text(
            value.get("attribution"),
            max_chars=_MAX_ATTRIBUTION_CHARS,
        ),
        "domain": domain,
    }


def _collect_source_candidates(reference: Any, *, footnote: bool) -> list[dict[str, str | None]]:
    if not isinstance(reference, dict):
        return []

    output: list[dict[str, str | None]] = []

    def push_candidate(value: Any) -> None:
        if len(output) >= _MAX_SOURCES_PER_REFERENCE:
            return
        candidate = _source_candidate(value)
        if candidate is not None:
            output.append(candidate)

    def push_item(value: Any) -> None:
        if not isinstance(value, dict):
            return
        push_candidate(value)
        supporting = value.get("supporting_websites")
        if isinstance(supporting, list):
            for source in supporting[:_MAX_SOURCES_PER_REFERENCE]:
                push_candidate(source)

    sources = reference.get("sources")
    if isinstance(sources, list):
        for source in sources[:_MAX_SOURCES_PER_REFERENCE]:
            push_item(source)

    if not footnote:
        items = reference.get("items")
        if isinstance(items, list):
            for item in items[:_MAX_SOURCES_PER_REFERENCE]:
                push_item(item)

        fallback_items = reference.get("fallback_items")
        if isinstance(fallback_items, list):
            for item in fallback_items[:_MAX_SOURCES_PER_REFERENCE]:
                push_item(item)

        if not output:
            push_candidate(reference)

    if not output:
        safe_urls = reference.get("safe_urls")
        if isinstance(safe_urls, list):
            for url in safe_urls[:_MAX_SOURCES_PER_REFERENCE]:
                push_candidate({"url": url, "title": url})

    deduped: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for candidate in output:
        url = candidate["url"]
        if not isinstance(url, str) or url in seen:
            continue
        seen.add(url)
        deduped.append(candidate)
    return deduped


def _exact_assistant_message(
    payload: Any,
    *,
    message_id: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    for _, node in _current_branch_nodes(payload):
        message = _message_from_node(node)
        if not isinstance(message, dict):
            continue
        if _optional_text(message.get("id")) != message_id:
            continue
        author = message.get("author")
        if not isinstance(author, dict) or _optional_text(author.get("role")) != "assistant":
            return None
        return message
    return None


def canonical_product_observation_events(
    payload: Any,
    *,
    message_id: str,
) -> tuple[dict[str, Any], ...]:
    """Normalize safe source/citation evidence from one exact canonical assistant message."""

    message_id = _optional_text(message_id) or ""
    if not message_id:
        return ()

    message = _exact_assistant_message(payload, message_id=message_id)
    if message is None:
        return ()

    metadata = message.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    if metadata.get("is_visually_hidden_from_conversation") is True:
        return ()

    content = message.get("content")
    content = content if isinstance(content, dict) else {}
    content_type = _optional_text(
        content.get("content_type"),
        max_chars=_MAX_REFERENCE_TYPE_CHARS,
    )
    if content_type is not None and content_type.casefold() == "thoughts":
        return ()

    events: list[dict[str, Any]] = []
    source_id_by_url: dict[str, str] = {}
    citation_keys: set[tuple[Any, ...]] = set()
    source_counter = 0
    citation_counter = 0

    def ensure_source(candidate: dict[str, str | None] | None, origin: str) -> str | None:
        nonlocal source_counter
        if candidate is None:
            return None
        url = candidate.get("url")
        if not isinstance(url, str):
            return None
        source_id = source_id_by_url.get(url)
        if source_id is not None:
            return source_id
        if len(source_id_by_url) >= _MAX_SOURCES_PER_TURN:
            return None
        source_counter += 1
        source_id = f"canonical:{message_id}:source:{source_counter}"
        source_id_by_url[url] = source_id
        events.append(
            {
                "type": "product_source_observed",
                "observation_schema": 1,
                "observation_id": f"source-observation:{source_id}",
                "source_id": source_id,
                "url": url,
                "title": candidate.get("title"),
                "domain": candidate.get("domain"),
                "attribution": candidate.get("attribution"),
                "source_origin": origin,
            }
        )
        return source_id

    def emit_citation(
        *,
        source_id: str | None,
        citation_index: int | None,
        start_index: Any,
        end_index: Any,
        reference_type: Any,
        display_text: Any,
    ) -> None:
        nonlocal citation_counter
        if source_id is None:
            return
        start = _non_negative_int(start_index)
        end = _non_negative_int(end_index)
        if start is None or end is None or end < start:
            return
        ref_type = _reference_type(reference_type)
        key = (source_id, start, end, citation_index, ref_type)
        if key in citation_keys:
            return
        citation_keys.add(key)
        citation_counter += 1
        citation_id = f"canonical:{message_id}:citation:{citation_counter}"
        events.append(
            {
                "type": "product_citation_observed",
                "observation_schema": 1,
                "observation_id": f"citation-observation:{citation_id}",
                "citation_id": citation_id,
                "source_id": source_id,
                "citation_index": citation_index,
                "start_index": start,
                "end_index": end,
                "reference_type": ref_type,
                "display_text": _optional_text(
                    display_text,
                    max_chars=_MAX_TITLE_CHARS,
                ),
            }
        )

    references = metadata.get("content_references")
    if isinstance(references, list):
        for reference_index, reference in enumerate(references[:_MAX_REFERENCES_PER_MESSAGE]):
            if not isinstance(reference, dict):
                continue
            ref_type = _reference_type(reference.get("type"))
            footnote = ref_type == "sources_footnote"
            for candidate in _collect_source_candidates(reference, footnote=footnote):
                source_id = ensure_source(
                    candidate,
                    "canonical_content_references.sources_footnote"
                    if footnote
                    else "canonical_content_references",
                )
                if footnote:
                    continue
                emit_citation(
                    source_id=source_id,
                    citation_index=reference_index,
                    start_index=reference.get("start_idx"),
                    end_index=reference.get("end_idx"),
                    reference_type=ref_type,
                    display_text=candidate.get("attribution") or candidate.get("title"),
                )

    citations = metadata.get("citations")
    if isinstance(citations, list):
        for citation_index, citation in enumerate(citations[:_MAX_REFERENCES_PER_MESSAGE]):
            if not isinstance(citation, dict):
                continue
            source = citation.get("metadata")
            source = source if isinstance(source, dict) else citation
            candidate = _source_candidate(source)
            source_id = ensure_source(candidate, "canonical_legacy_citations")
            emit_citation(
                source_id=source_id,
                citation_index=citation_index,
                start_index=citation.get("start_ix"),
                end_index=citation.get("end_ix"),
                reference_type=(
                    citation.get("citation_format_type")
                    or source.get("type")
                    or "legacy_citation"
                ),
                display_text=(
                    (candidate.get("attribution") or candidate.get("title"))
                    if candidate is not None
                    else None
                ),
            )

    cite_metadata = metadata.get("_cite_metadata")
    metadata_list = (
        cite_metadata.get("metadata_list")
        if isinstance(cite_metadata, dict)
        else None
    )
    if isinstance(metadata_list, list):
        for source in metadata_list[:_MAX_SOURCES_PER_REFERENCE]:
            ensure_source(_source_candidate(source), "canonical_legacy_cite_metadata")

    if content_type is not None and content_type.casefold() == "tether_quote":
        ensure_source(_source_candidate(content), "canonical_tether_quote")

    return tuple(events)


@dataclass
class _TurnObservationState:
    callback: Callable[[dict[str, Any]], None] | None
    source_id_by_url: dict[str, str] = field(default_factory=dict)
    url_by_source_id: dict[str, str] = field(default_factory=dict)
    citation_keys: set[tuple[Any, ...]] = field(default_factory=set)
    canonical_source_aliases: dict[str, str] = field(default_factory=dict)


_ACTIVE_TURN_STATE: ContextVar[_TurnObservationState | None] = ContextVar(
    "pr93_canonical_product_observation_state",
    default=None,
)


def _record_emitted_event(state: _TurnObservationState, event: dict[str, Any]) -> None:
    event_type = event.get("type")
    if event_type == "product_source_observed":
        url = _safe_source_url(event.get("url"))
        source_id = _optional_text(event.get("source_id"))
        if url is not None and source_id is not None:
            state.source_id_by_url.setdefault(url, source_id)
            state.url_by_source_id[source_id] = url
        return

    if event_type != "product_citation_observed":
        return
    source_id = _optional_text(event.get("source_id"))
    if source_id is None:
        return
    url = state.url_by_source_id.get(source_id)
    if url is None:
        return
    start = _non_negative_int(event.get("start_index"))
    end = _non_negative_int(event.get("end_index"))
    if start is None or end is None or end < start:
        return
    state.citation_keys.add(
        (
            url,
            start,
            end,
            _reference_type(event.get("reference_type")),
        )
    )


def _forward_canonical_events(
    state: _TurnObservationState,
    events: tuple[dict[str, Any], ...],
) -> None:
    for original_event in events:
        event = dict(original_event)
        event_type = event.get("type")

        if event_type == "product_source_observed":
            url = _safe_source_url(event.get("url"))
            source_id = _optional_text(event.get("source_id"))
            if url is None or source_id is None:
                continue
            existing_source_id = state.source_id_by_url.get(url)
            if existing_source_id is not None:
                state.canonical_source_aliases[source_id] = existing_source_id
                continue
            state.canonical_source_aliases[source_id] = source_id

        elif event_type == "product_citation_observed":
            source_id = _optional_text(event.get("source_id"))
            if source_id is None:
                continue
            source_id = state.canonical_source_aliases.get(source_id, source_id)
            event["source_id"] = source_id
            url = state.url_by_source_id.get(source_id)
            if url is None:
                # The matching canonical source must have been forwarded first.
                continue
            start = _non_negative_int(event.get("start_index"))
            end = _non_negative_int(event.get("end_index"))
            if start is None or end is None or end < start:
                continue
            key = (
                url,
                start,
                end,
                _reference_type(event.get("reference_type")),
            )
            if key in state.citation_keys:
                continue

        _record_emitted_event(state, event)
        if state.callback is None:
            continue
        try:
            state.callback(event)
        except Exception:
            # Canonical provenance is observation-only and must never invalidate
            # or replay the already delegated product write.
            pass


def _gate_wait_for_new_final_assistant(wait_for_final: Callable[..., Any]) -> Callable[..., Any]:
    if getattr(wait_for_final, _PR93_CANONICAL_OBSERVATION_GATE_MARKER, False):
        return wait_for_final

    @wraps(wait_for_final)
    def gated(*args: Any, **kwargs: Any) -> Any:
        result = wait_for_final(*args, **kwargs)
        state = _ACTIVE_TURN_STATE.get()
        if state is None or kwargs.get("include_readback") is not True:
            return result
        if not isinstance(result, tuple) or len(result) != 3:
            return result
        final_message, payload, _ = result
        message_id = _optional_text(getattr(final_message, "message_id", None))
        if message_id is None or not isinstance(payload, dict):
            return result
        events = canonical_product_observation_events(
            payload,
            message_id=message_id,
        )
        _forward_canonical_events(state, events)
        return result

    setattr(gated, _PR93_CANONICAL_OBSERVATION_GATE_MARKER, True)
    return gated


def _gate_send_browser_native(send_browser_native: Callable[..., Any]) -> Callable[..., Any]:
    if getattr(send_browser_native, _PR93_CANONICAL_OBSERVATION_GATE_MARKER, False):
        return send_browser_native

    @wraps(send_browser_native)
    def gated(self: Any, prompt: str, *args: Any, **kwargs: Any) -> Any:
        caller_on_event = kwargs.get("on_event")
        state = _TurnObservationState(callback=caller_on_event)

        def observe_and_forward(event: dict[str, Any]) -> None:
            if isinstance(event, dict):
                _record_emitted_event(state, event)
            if caller_on_event is not None:
                caller_on_event(event)

        if caller_on_event is not None:
            kwargs["on_event"] = observe_and_forward
        token = _ACTIVE_TURN_STATE.set(state)
        try:
            return send_browser_native(self, prompt, *args, **kwargs)
        finally:
            _ACTIVE_TURN_STATE.reset(token)

    setattr(gated, _PR93_CANONICAL_OBSERVATION_GATE_MARKER, True)
    return gated


def install_canonical_product_observation_gate() -> None:
    """Install canonical provenance observation without changing write/finality authority."""

    from . import browser_native_client as browser_native_client
    from . import browser_owned_write_runtime as browser_owned_write_runtime
    from .client import ChatGPTWebClient

    current_wait = browser_native_client._wait_for_new_final_assistant
    gated_wait = _gate_wait_for_new_final_assistant(current_wait)
    browser_native_client._wait_for_new_final_assistant = gated_wait

    current_send = browser_native_client.send_browser_native
    gated_send = _gate_send_browser_native(current_send)
    browser_native_client.send_browser_native = gated_send

    if browser_owned_write_runtime.send_browser_native is current_send:
        browser_owned_write_runtime.send_browser_native = gated_send

    if ChatGPTWebClient.send_browser_native is current_send:
        ChatGPTWebClient.send_browser_native = gated_send
