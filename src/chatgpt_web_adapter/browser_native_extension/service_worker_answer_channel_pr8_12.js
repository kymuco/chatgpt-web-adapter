// PR8.12: bounded assistant output-channel propagation for final-only streaming.
//
// Modern OpenAI assistant turns can distinguish user-visible `commentary`
// preambles from the terminal `final` answer. ChatGPT web payloads do not always
// expose this marker, so this layer treats it as optional evidence only. It
// exports a small normalized enum when present and never exports raw metadata.

const _pr812ChannelPriorVisibleAssistantText = _pr89BrowserStreamVisibleAssistantText;
const _pr812ChannelPriorRecordAssistant = _pr89BrowserStreamRecordAssistant;

function _pr812NormalizedAssistantChannel(value) {
  if (typeof value !== "string") return null;
  const normalized = value.trim().toLowerCase();
  if (normalized === "final" || normalized === "commentary") return normalized;
  return null;
}

function _pr812AssistantChannel(message) {
  if (!message || typeof message !== "object") return null;
  const metadata = message.metadata && typeof message.metadata === "object"
    ? message.metadata
    : {};
  for (const value of [
    message.channel,
    metadata.channel,
    metadata.output_channel,
    metadata.message_channel,
  ]) {
    const channel = _pr812NormalizedAssistantChannel(value);
    if (channel) return channel;
  }
  return null;
}

_pr89BrowserStreamVisibleAssistantText = function _pr812VisibleAssistantTextWithChannel(message) {
  const candidate = _pr812ChannelPriorVisibleAssistantText(message);
  if (!candidate) return candidate;
  return {
    ...candidate,
    channel: _pr812AssistantChannel(message),
  };
};

_pr89BrowserStreamRecordAssistant = async function _pr812RecordAssistantWithChannel(context, candidate) {
  if (!context || !candidate || typeof candidate !== "object") {
    return _pr812ChannelPriorRecordAssistant(context, candidate);
  }

  if (!(context.pr812AnswerChannelByKey instanceof Map)) {
    context.pr812AnswerChannelByKey = new Map();
  }

  const key = typeof candidate.messageKey === "string" && candidate.messageKey
    ? candidate.messageKey
    : null;
  const explicit = _pr812NormalizedAssistantChannel(candidate.channel);
  if (key && explicit) context.pr812AnswerChannelByKey.set(key, explicit);

  const remembered = key ? context.pr812AnswerChannelByKey.get(key) || null : null;
  return _pr812ChannelPriorRecordAssistant(context, {
    ...candidate,
    channel: explicit || remembered,
  });
};
