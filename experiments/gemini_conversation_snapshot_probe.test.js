const assert = require("assert");
const probe = require("./gemini_conversation_snapshot_probe.js");

const route1 = probe.parseGeminiConversationUrl(
  "https://gemini.google.com/app/abc123",
);
assert.equal(route1.rpcConversationId, "c_abc123");
assert.equal(route1.accountPrefix, "");
assert.equal(route1.sourcePath, "/app/abc123");

const route2 = probe.parseGeminiConversationUrl(
  "https://gemini.google.com/u/2/gem/gem42/c_def",
);
assert.equal(route2.rpcConversationId, "c_def");
assert.equal(route2.accountPrefix, "/u/2");
assert.equal(route2.gemId, "gem42");

const payload = [
  [
    [[null, "r-new"], null, [["new user"]], [[["rc_new", ["new answer"]]]]],
    [[null, "r-old"], null, [["old user"]], [[["rc_old", ["old answer"]]]]],
  ],
];
const normalized = probe.normalizeConversationPayload(payload, "c_demo");
assert.deepEqual(
  normalized.messages.map((message) => [message.role, message.text]),
  [
    ["user", "old user"],
    ["assistant", "old answer"],
    ["user", "new user"],
    ["assistant", "new answer"],
  ],
);
assert(
  probe
    .renderMarkdownContext(normalized.messages)
    .includes("## USER\n\nold user"),
);

const payloadString = JSON.stringify(payload);
const frame = JSON.stringify([
  ["wrb.fr", "hNvQHb", payloadString, null, null, null, "generic"],
]);
const response = `)]}'\n${frame.length}\n${frame}\n`;
const decoded = probe.parseBatchExecuteResponse(response);
assert.deepEqual(decoded[0], payload);

const html =
  '<script>window.WIZ_global_data={"SNlM0e":"token123","cfb2h":"build456","FdrFJe":"sid789"}</script>';
const bootstrap = probe.extractBootstrap(html);
assert.equal(bootstrap.at, "token123");
assert.equal(bootstrap.buildLabel, "build456");
assert.equal(bootstrap.sessionId, "sid789");

console.log("gemini snapshot probe parser tests: OK");
