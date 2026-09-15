// Shared request-text shape compatibility.
//
// Current ChatGPT request bodies can encode textual content either as bare
// string parts or as bounded object parts carrying a string `text` field. Some
// payloads also expose the same text through `content.text` when no textual
// parts are present. Schema 29 historically recognizes only bare string parts,
// which can make a successfully submitted ordinary turn look foreign even when
// the exact request body is available.
//
// Normalize only these already-textual representations before the existing
// schema-29 inspector runs. Attachment pointers remain attachment objects,
// unknown object parts remain untouched, and schema 29 still owns all authority:
// exact text equality, action=next, conversation semantics, message identity,
// and attachment counts. No fuzzy matching, request mutation, retry, fallback,
// route inference, or new authority is introduced.

const CWA_REQUEST_TEXT_SHAPE_COMPAT_SCHEMA = 1;
const CWA_REQUEST_TEXT_SHAPE_DIAGNOSTIC_KEY =
  "cwa_pr14_2_request_correlation_fingerprint";
const _cwaRequestTextShapePriorSchema29Inspect =
  _pr92Schema29InspectRequestPostData;

function _cwaRequestTextShapeNormalizedPostData(postData) {
  if (typeof postData !== "string" || !postData) return postData;

  let payload;
  try {
    payload = JSON.parse(postData);
  } catch {
    return postData;
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return postData;
  }
  if (!Array.isArray(payload.messages)) return postData;

  let payloadChanged = false;
  const messages = payload.messages.map((message) => {
    if (message === null || typeof message !== "object" || Array.isArray(message)) {
      return message;
    }
    const content = message.content;
    if (content === null || typeof content !== "object" || Array.isArray(content)) {
      return message;
    }

    const parts = Array.isArray(content.parts) ? content.parts : [];
    let messageChanged = false;
    let visibleText = "";
    const normalizedParts = parts.map((part) => {
      if (typeof part === "string") {
        visibleText += part;
        return part;
      }
      if (part === null || typeof part !== "object" || Array.isArray(part)) {
        return part;
      }

      // Attachment identity wins over any incidental text-like field.
      if (typeof part.asset_pointer === "string" && part.asset_pointer.trim()) {
        return part;
      }
      if (typeof part.text === "string") {
        visibleText += part.text;
        messageChanged = true;
        return part.text;
      }
      return part;
    });

    if (!visibleText.trim() && typeof content.text === "string") {
      normalizedParts.push(content.text);
      messageChanged = true;
    }
    if (!messageChanged) return message;

    payloadChanged = true;
    return {
      ...message,
      content: {
        ...content,
        parts: normalizedParts
      }
    };
  });

  if (!payloadChanged) return postData;
  return JSON.stringify({ ...payload, messages });
}

function _cwaRequestTextShapeCommonPrefixLength(left, right) {
  const limit = Math.min(left.length, right.length);
  let index = 0;
  while (index < limit && left[index] === right[index]) index += 1;
  return index;
}

function _cwaRequestTextShapeCommonSuffixLength(left, right) {
  const limit = Math.min(left.length, right.length);
  let count = 0;
  while (
    count < limit &&
    left[left.length - 1 - count] === right[right.length - 1 - count]
  ) {
    count += 1;
  }
  return count;
}

function _cwaRequestTextShapeCollectSafeFingerprint(
  postData,
  expectedText,
  result,
  expectedConversationId
) {
  const diagnostics = result?.diagnostics || {};
  const fingerprint = {
    matched: result?.matched === true,
    requestJsonParsed: diagnostics.requestJsonParsed === true,
    actionNext: diagnostics.actionNext === true,
    conversationIdentityMatches:
      diagnostics.conversationIdentityMatches === true,
    expectedConversationIdPresent:
      typeof expectedConversationId === "string" && Boolean(expectedConversationId.trim()),
    userMessageCount: Number(diagnostics.userMessageCount) || 0,
    userMessageIdCount: Number(diagnostics.userMessageIdCount) || 0,
    userMessageIdentityClassified:
      diagnostics.userMessageIdentityClassified === true,
    exactTextUserMessageCount:
      Number(diagnostics.exactTextUserMessageCount) || 0,
    exactRichUserMessageCount:
      Number(diagnostics.exactRichUserMessageCount) || 0,
    pointerPartCount: Number(diagnostics.pointerPartCount) || 0,
    metadataAttachmentCount:
      Number(diagnostics.metadataAttachmentCount) || 0,
    attachmentEvidenceChannelCount:
      Number(diagnostics.attachmentEvidenceChannelCount) || 0,
    attachmentCountsMatch: diagnostics.attachmentCountsMatch === true,
    expectedTextLength:
      typeof expectedText === "string" ? expectedText.length : -1,
    observedTextLength: -1,
    observedTextCandidateCount: 0,
    stringPartCount: 0,
    objectTextPartCount: 0,
    assetPointerPartCount: 0,
    unknownPartCount: 0,
    contentTextFallbackCount: 0,
    exactObservedTextEqualsExpected: false,
    crlfNormalizedEqualsExpected: false,
    nfcNormalizedEqualsExpected: false,
    trimEqualsExpected: false,
    commonPrefixLength: 0,
    commonSuffixLength: 0
  };

  if (typeof postData !== "string" || !postData || typeof expectedText !== "string") {
    return fingerprint;
  }

  let payload;
  try {
    payload = JSON.parse(postData);
  } catch {
    return fingerprint;
  }
  if (!Array.isArray(payload?.messages)) return fingerprint;

  const observedTexts = [];
  for (const message of payload.messages) {
    if (message?.author?.role !== "user") continue;
    const content = message?.content;
    if (content === null || typeof content !== "object" || Array.isArray(content)) {
      continue;
    }
    const parts = Array.isArray(content.parts) ? content.parts : [];
    let text = "";
    let visibleTextFound = false;
    for (const part of parts) {
      if (typeof part === "string") {
        fingerprint.stringPartCount += 1;
        text += part;
        visibleTextFound = true;
        continue;
      }
      if (part === null || typeof part !== "object" || Array.isArray(part)) {
        fingerprint.unknownPartCount += 1;
        continue;
      }
      if (typeof part.asset_pointer === "string" && part.asset_pointer.trim()) {
        fingerprint.assetPointerPartCount += 1;
        continue;
      }
      if (typeof part.text === "string") {
        fingerprint.objectTextPartCount += 1;
        text += part.text;
        visibleTextFound = true;
        continue;
      }
      fingerprint.unknownPartCount += 1;
    }
    if (!visibleTextFound && typeof content.text === "string") {
      fingerprint.contentTextFallbackCount += 1;
      text = content.text;
      visibleTextFound = true;
    }
    if (visibleTextFound) observedTexts.push(text);
  }

  fingerprint.observedTextCandidateCount = observedTexts.length;
  if (observedTexts.length !== 1) return fingerprint;

  const observedText = observedTexts[0];
  fingerprint.observedTextLength = observedText.length;
  fingerprint.exactObservedTextEqualsExpected = observedText === expectedText;
  fingerprint.crlfNormalizedEqualsExpected =
    observedText.replace(/\r\n?/g, "\n") === expectedText.replace(/\r\n?/g, "\n");
  try {
    fingerprint.nfcNormalizedEqualsExpected =
      observedText.normalize("NFC") === expectedText.normalize("NFC");
  } catch {
    fingerprint.nfcNormalizedEqualsExpected = false;
  }
  fingerprint.trimEqualsExpected = observedText.trim() === expectedText.trim();
  fingerprint.commonPrefixLength = _cwaRequestTextShapeCommonPrefixLength(
    observedText,
    expectedText
  );
  fingerprint.commonSuffixLength = _cwaRequestTextShapeCommonSuffixLength(
    observedText,
    expectedText
  );
  return fingerprint;
}

function _cwaRequestTextShapePersistSafeFingerprint(fingerprint) {
  try {
    const set = globalThis?.chrome?.storage?.local?.set;
    if (typeof set !== "function") return;
    const pending = set.call(globalThis.chrome.storage.local, {
      [CWA_REQUEST_TEXT_SHAPE_DIAGNOSTIC_KEY]: fingerprint
    });
    if (pending && typeof pending.catch === "function") pending.catch(() => {});
  } catch {
    // Safe observability must never perturb request correlation.
  }
}

_pr92Schema29InspectRequestPostData = function _cwaRequestTextShapeInspect(
  postData,
  expectedText,
  expectedAttachmentCount,
  expectedConversationId
) {
  const normalizedPostData = _cwaRequestTextShapeNormalizedPostData(postData);
  const result = _cwaRequestTextShapePriorSchema29Inspect(
    normalizedPostData,
    expectedText,
    expectedAttachmentCount,
    expectedConversationId
  );
  _cwaRequestTextShapePersistSafeFingerprint(
    _cwaRequestTextShapeCollectSafeFingerprint(
      postData,
      expectedText,
      result,
      expectedConversationId
    )
  );
  return result;
};
