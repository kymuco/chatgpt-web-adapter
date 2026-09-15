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

_pr92Schema29InspectRequestPostData = function _cwaRequestTextShapeInspect(
  postData,
  expectedText,
  expectedAttachmentCount,
  expectedConversationId
) {
  return _cwaRequestTextShapePriorSchema29Inspect(
    _cwaRequestTextShapeNormalizedPostData(postData),
    expectedText,
    expectedAttachmentCount,
    expectedConversationId
  );
};
