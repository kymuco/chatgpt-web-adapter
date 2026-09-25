// Browser-composer indentation correlation compatibility.
//
// Live product evidence proved an ordinary request whose observed and expected
// texts had identical length, one exact user message identity, and a first
// mismatch exactly at the first two-space JSON indentation emitted by a pretty
// printer. Contenteditable composers may preserve line-leading ASCII indentation
// with non-breaking Unicode space code points before ChatGPT serializes the
// request body.
//
// This layer does not normalize whitespace generally. It permits only one
// browser-composer equivalence for ordinary text with zero attachments:
// expected ASCII spaces may correspond to U+00A0 NBSP or U+202F NNBSP while
// still inside line-leading indentation. Total length must be identical and
// every other code unit must match exactly. The request sent on the network is
// never changed; only a local correlation copy is canonicalized before the
// already-reviewed text-shape/schema-29 inspector runs.

const CWA_BROWSER_INDENT_COMPAT_SCHEMA = 1;
const CWA_BROWSER_INDENT_DIAGNOSTIC_KEY =
  "cwa_browser_indent_correlation_fingerprint";
function _cwaBrowserIndentEquivalent(observedText, expectedText) {
  const result = {
    equivalent: false,
    normalizedIndentSpaceCount: 0
  };
  if (typeof observedText !== "string" || typeof expectedText !== "string") {
    return result;
  }
  if (observedText.length !== expectedText.length) return result;

  let inLeadingIndent = true;
  let normalized = 0;
  for (let index = 0; index < expectedText.length; index += 1) {
    const expected = expectedText[index];
    const observed = observedText[index];

    if (expected === observed) {
      if (expected === "\n") {
        inLeadingIndent = true;
      } else if (inLeadingIndent && expected !== " ") {
        inLeadingIndent = false;
      }
      continue;
    }

    if (
      inLeadingIndent &&
      expected === " " &&
      (observed === "\u00a0" || observed === "\u202f")
    ) {
      normalized += 1;
      continue;
    }
    return result;
  }

  result.equivalent = normalized > 0;
  result.normalizedIndentSpaceCount = normalized;
  return result;
}

function _cwaBrowserIndentVisibleOrdinaryText(message) {
  if (message === null || typeof message !== "object" || Array.isArray(message)) {
    return null;
  }
  if (message?.author?.role !== "user") return null;
  const content = message.content;
  if (content === null || typeof content !== "object" || Array.isArray(content)) {
    return null;
  }

  const metadataAttachments = Array.isArray(message?.metadata?.attachments)
    ? message.metadata.attachments
    : [];
  if (metadataAttachments.length !== 0) return null;

  const parts = Array.isArray(content.parts) ? content.parts : [];
  let visibleText = "";
  let visibleTextFound = false;
  for (const part of parts) {
    if (typeof part === "string") {
      visibleText += part;
      visibleTextFound = true;
      continue;
    }
    if (part === null || typeof part !== "object" || Array.isArray(part)) {
      return null;
    }
    if (typeof part.asset_pointer === "string" && part.asset_pointer.trim()) {
      return null;
    }
    if (typeof part.text === "string") {
      visibleText += part.text;
      visibleTextFound = true;
      continue;
    }
    return null;
  }

  if (!visibleTextFound && typeof content.text === "string") {
    visibleText = content.text;
    visibleTextFound = true;
  }
  return visibleTextFound ? visibleText : null;
}

function _cwaBrowserIndentCanonicalizedPostData(postData, expectedText) {
  const outcome = {
    postData,
    eligibleOrdinaryRequest: false,
    observedTextCandidateCount: 0,
    observedTextLength: -1,
    browserIndentEquivalent: false,
    normalizedIndentSpaceCount: 0
  };
  if (typeof postData !== "string" || !postData || typeof expectedText !== "string") {
    return outcome;
  }

  let payload;
  try {
    payload = JSON.parse(postData);
  } catch {
    return outcome;
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return outcome;
  }
  if (!Array.isArray(payload.messages)) return outcome;

  const candidates = [];
  for (let index = 0; index < payload.messages.length; index += 1) {
    const message = payload.messages[index];
    const visibleText = _cwaBrowserIndentVisibleOrdinaryText(message);
    if (visibleText !== null) candidates.push({ index, message, visibleText });
  }
  outcome.observedTextCandidateCount = candidates.length;
  if (candidates.length !== 1) return outcome;

  const candidate = candidates[0];
  outcome.eligibleOrdinaryRequest = true;
  outcome.observedTextLength = candidate.visibleText.length;
  const equivalence = _cwaBrowserIndentEquivalent(
    candidate.visibleText,
    expectedText
  );
  outcome.browserIndentEquivalent = equivalence.equivalent;
  outcome.normalizedIndentSpaceCount = equivalence.normalizedIndentSpaceCount;
  if (!equivalence.equivalent) return outcome;

  const messages = payload.messages.slice();
  messages[candidate.index] = {
    ...candidate.message,
    content: {
      ...candidate.message.content,
      parts: [expectedText]
    }
  };
  outcome.postData = JSON.stringify({ ...payload, messages });
  return outcome;
}

function _cwaBrowserIndentPersistSafeFingerprint(fingerprint) {
  try {
    const set = globalThis?.chrome?.storage?.local?.set;
    if (typeof set !== "function") return;
    const pending = set.call(globalThis.chrome.storage.local, {
      [CWA_BROWSER_INDENT_DIAGNOSTIC_KEY]: fingerprint
    });
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  } catch {
    // Safe observability must never perturb request correlation.
  }
}

function _cwaBrowserIndentInspect(
  postData,
  expectedText,
  expectedAttachmentCount,
  expectedConversationId
) {
  const prior = _cwaRequestTextShapeInspect(
    postData,
    expectedText,
    expectedAttachmentCount,
    expectedConversationId
  );
  if (prior?.matched === true || expectedAttachmentCount !== 0) {
    _cwaBrowserIndentPersistSafeFingerprint({
      priorMatched: prior?.matched === true,
      eligibleOrdinaryRequest: false,
      observedTextCandidateCount: 0,
      expectedTextLength: typeof expectedText === "string" ? expectedText.length : -1,
      observedTextLength: -1,
      browserIndentEquivalent: false,
      normalizedIndentSpaceCount: 0,
      normalizedMatch: false
    });
    return prior;
  }

  const canonicalized = _cwaBrowserIndentCanonicalizedPostData(
    postData,
    expectedText
  );
  let result = prior;
  if (canonicalized.browserIndentEquivalent) {
    result = _cwaRequestTextShapeInspect(
      canonicalized.postData,
      expectedText,
      expectedAttachmentCount,
      expectedConversationId
    );
  }

  _cwaBrowserIndentPersistSafeFingerprint({
    priorMatched: prior?.matched === true,
    eligibleOrdinaryRequest: canonicalized.eligibleOrdinaryRequest,
    observedTextCandidateCount: canonicalized.observedTextCandidateCount,
    expectedTextLength: typeof expectedText === "string" ? expectedText.length : -1,
    observedTextLength: canonicalized.observedTextLength,
    browserIndentEquivalent: canonicalized.browserIndentEquivalent,
    normalizedIndentSpaceCount: canonicalized.normalizedIndentSpaceCount,
    normalizedMatch: result?.matched === true
  });
  return result;
}
