// PR9.3: structured source/citation observations above the PR8.12 activity stream.
//
// This layer observes only bounded product-visible provenance fields already
// present in streamed ChatGPT messages. It does not read response bodies, raw
// tool arguments/results, hidden messages, private thoughts, credentials, DOM,
// cookies, headers, or request post data. Observation defects are non-authority:
// they cannot fail/retry a product write or replace canonical finality.

const PR93_SOURCE_CITATION_SCHEMA_VERSION = 1;
const PR93_MAX_SOURCES_PER_REFERENCE = 64;
const PR93_MAX_SOURCES_PER_TURN = 128;
const PR93_MAX_REFERENCES_PER_MESSAGE = 128;
const PR93_MAX_URL_CHARS = 4096;
const PR93_MAX_TITLE_CHARS = 512;
const PR93_MAX_ATTRIBUTION_CHARS = 256;
const PR93_MAX_REFERENCE_TYPE_CHARS = 96;

const _pr93PriorInspectMessage = _pr812InspectMessage;
const _pr93StateByStreamContext = new WeakMap();

function _pr93State(context) {
  let state = _pr93StateByStreamContext.get(context);
  if (state) return state;
  state = {
    sourceIdByKey: new Map(),
    emittedSourceIds: new Set(),
    emittedCitationKeys: new Set(),
    sourceCounter: 0,
    citationCounter: 0
  };
  _pr93StateByStreamContext.set(context, state);
  return state;
}

function _pr93BoundedText(value, maxChars) {
  if (typeof value !== "string") return null;
  const normalized = value.replace(/\u0000/g, "").trim();
  if (!normalized) return null;
  return normalized.slice(0, maxChars);
}

function _pr93OptionalNonNegativeInt(value) {
  return Number.isInteger(value) && value >= 0 ? value : null;
}

function _pr93SafeReferenceType(value) {
  const text = _pr93BoundedText(value, PR93_MAX_REFERENCE_TYPE_CHARS);
  if (!text) return null;
  return text.toLowerCase().replace(/[^a-z0-9_.:-]+/g, "_").slice(0, PR93_MAX_REFERENCE_TYPE_CHARS) || null;
}

function _pr93SafeHttpUrl(value) {
  const text = _pr93BoundedText(value, PR93_MAX_URL_CHARS);
  if (!text) return null;
  try {
    const parsed = new URL(text);
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return null;
    // Never export URLs containing explicit userinfo credentials.
    if (parsed.username || parsed.password) return null;
    return parsed.href.slice(0, PR93_MAX_URL_CHARS);
  } catch {
    return null;
  }
}

function _pr93SourceCandidate(value) {
  if (!value || typeof value !== "object") return null;
  const url = _pr93SafeHttpUrl(value.url);
  if (!url) return null;
  let domain = null;
  try { domain = new URL(url).hostname || null; } catch {}
  return {
    url,
    title: _pr93BoundedText(value.title, PR93_MAX_TITLE_CHARS),
    attribution: _pr93BoundedText(value.attribution, PR93_MAX_ATTRIBUTION_CHARS),
    domain
  };
}

function _pr93CollectSourceCandidates(reference, options = {}) {
  const footnote = options?.footnote === true;
  const output = [];
  const pushCandidate = (value) => {
    if (output.length >= PR93_MAX_SOURCES_PER_REFERENCE) return;
    const candidate = _pr93SourceCandidate(value);
    if (candidate) output.push(candidate);
  };
  const pushItem = (item) => {
    if (!item || typeof item !== "object") return;
    pushCandidate(item);
    const supporting = Array.isArray(item.supporting_websites)
      ? item.supporting_websites.slice(0, PR93_MAX_SOURCES_PER_REFERENCE)
      : [];
    for (const source of supporting) pushCandidate(source);
  };

  if (!reference || typeof reference !== "object") return output;

  if (footnote && Array.isArray(reference.sources) && reference.sources.length) {
    for (const source of reference.sources.slice(0, PR93_MAX_SOURCES_PER_REFERENCE)) pushItem(source);
  } else {
    const items = Array.isArray(reference.items) ? reference.items : [];
    for (const item of items.slice(0, PR93_MAX_SOURCES_PER_REFERENCE)) pushItem(item);

    const fallback = Array.isArray(reference.fallback_items) ? reference.fallback_items : [];
    for (const item of fallback.slice(0, PR93_MAX_SOURCES_PER_REFERENCE)) pushItem(item);

    if (output.length === 0) pushCandidate(reference);
  }

  if (output.length === 0 && Array.isArray(reference.safe_urls)) {
    for (const url of reference.safe_urls.slice(0, PR93_MAX_SOURCES_PER_REFERENCE)) {
      pushCandidate({ url, title: url });
    }
  }

  const seen = new Set();
  return output.filter((candidate) => {
    if (seen.has(candidate.url)) return false;
    seen.add(candidate.url);
    return true;
  });
}

function _pr93EnsureSource(context, state, candidate, origin) {
  if (!candidate) return null;
  let sourceId = state.sourceIdByKey.get(candidate.url);
  if (!sourceId) {
    if (state.sourceIdByKey.size >= PR93_MAX_SOURCES_PER_TURN) return null;
    state.sourceCounter += 1;
    sourceId = `pr93-source-${state.sourceCounter}`;
    state.sourceIdByKey.set(candidate.url, sourceId);
  }

  if (!state.emittedSourceIds.has(sourceId)) {
    state.emittedSourceIds.add(sourceId);
    _pr812Emit(context, {
      type: "product_source_observed",
      observation_schema: PR93_SOURCE_CITATION_SCHEMA_VERSION,
      observation_id: `source-observation:${sourceId}`,
      source_id: sourceId,
      url: candidate.url,
      title: candidate.title,
      domain: candidate.domain,
      attribution: candidate.attribution,
      source_origin: _pr93SafeReferenceType(origin)
    });
  }
  return sourceId;
}

function _pr93EmitCitation(context, state, fields) {
  const sourceId = fields?.sourceId;
  if (typeof sourceId !== "string" || !sourceId) return;
  const startIndex = _pr93OptionalNonNegativeInt(fields.startIndex);
  const endIndex = _pr93OptionalNonNegativeInt(fields.endIndex);
  const citationIndex = _pr93OptionalNonNegativeInt(fields.citationIndex);
  const referenceType = _pr93SafeReferenceType(fields.referenceType);
  const messageId = _pr93BoundedText(fields.messageId, 256) || "message";

  const key = [messageId, sourceId, startIndex, endIndex, citationIndex, referenceType].join("|");
  if (state.emittedCitationKeys.has(key)) return;
  state.emittedCitationKeys.add(key);
  state.citationCounter += 1;
  const citationId = `pr93-citation-${state.citationCounter}`;

  _pr812Emit(context, {
    type: "product_citation_observed",
    observation_schema: PR93_SOURCE_CITATION_SCHEMA_VERSION,
    observation_id: `citation-observation:${citationId}`,
    citation_id: citationId,
    source_id: sourceId,
    citation_index: citationIndex,
    start_index: startIndex,
    end_index: endIndex,
    reference_type: referenceType,
    display_text: _pr93BoundedText(fields.displayText, PR93_MAX_TITLE_CHARS)
  });
}

function _pr93InspectContentReferences(context, state, messageId, metadata) {
  const references = Array.isArray(metadata?.content_references)
    ? metadata.content_references.slice(0, PR93_MAX_REFERENCES_PER_MESSAGE)
    : [];

  references.forEach((reference, referenceIndex) => {
    if (!reference || typeof reference !== "object") return;
    const referenceType = _pr93SafeReferenceType(reference.type);
    const footnote = referenceType === "sources_footnote";
    const candidates = _pr93CollectSourceCandidates(reference, { footnote });
    const startIndex = _pr93OptionalNonNegativeInt(reference.start_idx);
    const endIndex = _pr93OptionalNonNegativeInt(reference.end_idx);

    for (const candidate of candidates) {
      const sourceId = _pr93EnsureSource(
        context,
        state,
        candidate,
        footnote ? "content_references.sources_footnote" : "content_references"
      );
      if (!sourceId || footnote) continue;
      _pr93EmitCitation(context, state, {
        sourceId,
        messageId,
        citationIndex: referenceIndex,
        startIndex,
        endIndex,
        referenceType,
        displayText: candidate.attribution || candidate.title
      });
    }
  });
}

function _pr93InspectLegacyCitations(context, state, messageId, metadata) {
  const citations = Array.isArray(metadata?.citations)
    ? metadata.citations.slice(0, PR93_MAX_REFERENCES_PER_MESSAGE)
    : [];

  citations.forEach((citation, citationIndex) => {
    if (!citation || typeof citation !== "object") return;
    const source = citation.metadata && typeof citation.metadata === "object"
      ? citation.metadata
      : citation;
    const candidate = _pr93SourceCandidate(source);
    const sourceId = _pr93EnsureSource(context, state, candidate, "legacy_citations");
    if (!sourceId) return;
    _pr93EmitCitation(context, state, {
      sourceId,
      messageId,
      citationIndex,
      startIndex: citation.start_ix,
      endIndex: citation.end_ix,
      referenceType: citation.citation_format_type || source.type || "legacy_citation",
      displayText: candidate.attribution || candidate.title
    });
  });

  const metadataList = Array.isArray(metadata?._cite_metadata?.metadata_list)
    ? metadata._cite_metadata.metadata_list.slice(0, PR93_MAX_SOURCES_PER_REFERENCE)
    : [];
  for (const source of metadataList) {
    _pr93EnsureSource(context, state, _pr93SourceCandidate(source), "legacy_cite_metadata");
  }
}

function _pr93InspectTetherQuote(context, state, content) {
  if (!content || typeof content !== "object" || content.content_type !== "tether_quote") return;
  const candidate = _pr93SourceCandidate(content);
  _pr93EnsureSource(context, state, candidate, "tether_quote");
}

_pr812InspectMessage = function _pr812InspectMessageWithStructuredSources(context, priorState, message) {
  _pr93PriorInspectMessage(context, priorState, message);

  if (!message || typeof message !== "object") return;
  if (message?.metadata?.is_visually_hidden_from_conversation === true) return;

  const content = message.content && typeof message.content === "object" ? message.content : {};
  if (content.content_type === "thoughts") return;

  const metadata = message.metadata && typeof message.metadata === "object" ? message.metadata : {};
  const messageId = _pr93BoundedText(message.id, 256) || "message";
  const state = _pr93State(context);

  _pr93InspectContentReferences(context, state, messageId, metadata);
  _pr93InspectLegacyCitations(context, state, messageId, metadata);
  _pr93InspectTetherQuote(context, state, content);
};
