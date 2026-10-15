// Observe Qwen's own request. Never issue or replay a completion request.
function _cwaQwenSseParser(onDelta) {
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;
  return {
    push(base64) {
      if (finished || !base64) return;
      buffer += decoder.decode(Uint8Array.from(atob(base64), c => c.charCodeAt(0)), {stream: true});
      let end;
      while ((end = buffer.indexOf("\n\n")) >= 0 || (end = buffer.indexOf("\r\n\r\n")) >= 0) {
        const width = buffer.startsWith("\r\n\r\n", end) ? 4 : 2;
        const frame = buffer.slice(0, end);
        buffer = buffer.slice(end + width);
        const data = frame.split(/\r?\n/).filter(line => line.startsWith("data:"))
          .map(line => line.slice(5).trimStart()).join("\n");
        if (!data) continue;
        if (data === "[DONE]") { finished = true; break; }
        let event;
        try { event = JSON.parse(data); } catch { continue; }
        const delta = event?.choices?.[0]?.delta;
        if (delta?.phase === "answer" && typeof delta.content === "string" && delta.content) onDelta(delta.content);
        if (delta?.phase === "answer" && delta.status === "finished") { finished = true; break; }
      }
      if (buffer.length > 4 * 1024 * 1024) throw new Error("QWEN_STREAM_FRAME_TOO_LARGE");
    },
    get finished() { return finished; }
  };
}

async function _cwaQwenObserveStream(debuggee, message) {
  let requestId = null, ready = false, closed = false, failure = null;
  let pending = [], count = 0;
  let answerText = "";
  let enabling = Promise.resolve();
  const parser = _cwaQwenSseParser(text => {
    count++;
    answerText += text;
    postNative({protocol: BRIDGE_PROTOCOL_VERSION, type: "turn_event",
      request_id: message.request_id,
      event: {providerId: "qwen", type: "text_delta", text}});
  });
  const consume = data => {
    if (!data || closed || failure) return;
    try { parser.push(data); } catch { failure = "QWEN_NETWORK_STREAM_PARSE_FAILED"; }
  };
  const observer = (source, method, params) => {
    if (closed || source.tabId !== debuggee.tabId) return;
    if (method === "Network.requestWillBeSent" && requestId === null) {
      try {
        const url = new URL(params.request.url);
        if (url.origin === "https://chat.qwen.ai" && url.pathname === "/api/v2/chat/completions" && params.request.method === "POST") {
          // Only bind the turn we submitted, not another request in the tab.
          const body = JSON.parse(params.request.postData || "null");
          if (message.operation === "regenerate" || body?.messages?.some(item => item.role === "user" && item.content === message.text)) requestId = params.requestId;
        }
      } catch {}
    }
    if (params.requestId !== requestId || requestId === null) return;
    if (method === "Network.responseReceived") {
      if (params.response.status !== 200 || !params.response.mimeType.includes("text/event-stream")) {
        failure = "QWEN_NETWORK_STREAM_NON_SSE";
        return;
      }
      enabling = _cwaBaseSendCommand(debuggee, "Network.streamResourceContent", {requestId})
        .then(result => {
          if (closed) return;
          consume(result?.bufferedData);
          ready = true;
          for (const data of pending) consume(data);
          pending = [];
        }).catch(() => { failure = "QWEN_NETWORK_STREAM_UNAVAILABLE"; pending = []; });
    } else if (method === "Network.dataReceived" && params.data) {
      if (ready) consume(params.data);
      else pending.push(params.data);
    } else if (method === "Network.loadingFailed") failure = "QWEN_NETWORK_STREAM_INTERRUPTED";
  };
  chrome.debugger.onEvent.addListener(observer);
  try { await _cwaBaseSendCommand(debuggee, "Network.enable", {maxPostDataSize: 1048576}); }
  catch (error) { chrome.debugger.onEvent.removeListener(observer); throw error; }
  return {
    get completed() { return ready && !failure && count > 0 && parser.finished; },
    async verify() {
      await enabling;
      if (failure || !count || !parser.finished) throw new Error(failure || "QWEN_NETWORK_STREAM_INCOMPLETE");
      return answerText;
    },
    close() { closed = true; chrome.debugger.onEvent.removeListener(observer); pending = []; }
  };
}
