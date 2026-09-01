// PR10.1: probe-anchored structural characterization for generated artifacts.
//
// The first authenticated artifact-generation probe proved that ChatGPT created the
// requested file but the current explicit-id observer saw no artifact identity. This
// diagnostic therefore inspects raw SSE payload structure only inside the worker and
// only around the fixed harmless probe filename. It never exports raw payload values,
// text, locators, credentials, bytes, DOM, or private reasoning.

const PR101_ARTIFACT_SHAPE_EVENT = "product_artifact_shape_observed";
const PR101_ARTIFACT_SHAPE_SCHEMA_VERSION = 1;
const PR101_ARTIFACT_SHAPE_PROBE_FILENAME = "cwa_pr10_1_probe.txt";
const PR101_ARTIFACT_SHAPE_MAX_DEPTH = 10;
const PR101_ARTIFACT_SHAPE_MAX_KEYS = 96;
const PR101_ARTIFACT_SHAPE_MAX_NODES = 2048;
const PR101_ARTIFACT_SHAPE_MAX_FINDINGS = 16;
const PR101_ARTIFACT_SHAPE_MAX_JSON_TEXT = 200000;

const _pr101ShapePriorProcessSseEvent = _pr89BrowserStreamProcessSseEvent;
const _pr101ShapePriorExecuteNativeTurn = executeNativeTurn;
const _pr101ShapeEmissionState = new WeakMap();

function _pr101ShapeSafeKey(value) {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text || text.length > 80 || !/^[A-Za-z0-9_.:-]+$/.test(text)) return null;
  const lower = text.toLowerCase();
  if (
    lower.includes("token") || lower.includes("secret") ||
    lower.includes("credential") || lower.includes("authorization") ||
    lower.includes("cookie") || lower.includes("password")
  ) return null;
  return lower.slice(0, 80);
}

function _pr101ShapePrivateOrPromptObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  if (value?.metadata?.is_visually_hidden_from_conversation === true) return true;
  if (value?.content_type === "thoughts" || value?.content?.content_type === "thoughts") return true;
  if (value?.author?.role === "user") return true;
  return false;
}

function _pr101ShapeAnchorKind(value) {
  if (typeof value !== "string" || value.length > 2048) return null;
  if (value === PR101_ARTIFACT_SHAPE_PROBE_FILENAME) return "exact_filename";
  if (
    value.endsWith(`/${PR101_ARTIFACT_SHAPE_PROBE_FILENAME}`) ||
    value.endsWith(`\\${PR101_ARTIFACT_SHAPE_PROBE_FILENAME}`)
  ) return "filename_suffix";
  return null;
}

function _pr101ShapeParentKeys(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  const output = [];
  for (const key of Object.keys(value).slice(0, PR101_ARTIFACT_SHAPE_MAX_KEYS)) {
    const safe = _pr101ShapeSafeKey(key);
    if (safe) output.push(safe);
  }
  return Array.from(new Set(output)).sort().slice(0, 32);
}

function _pr101ShapePath(path) {
  return path.join(".").slice(0, 640);
}

function _pr101ShapeMaybeParseJsonString(value) {
  if (typeof value !== "string" || value.length > PR101_ARTIFACT_SHAPE_MAX_JSON_TEXT) return null;
  if (!value.includes(PR101_ARTIFACT_SHAPE_PROBE_FILENAME)) return null;
  const text = value.trim();
  if (!(text.startsWith("{") || text.startsWith("["))) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function _pr101ShapeFindings(root) {
  const findings = [];
  const budget = { nodes: 0 };

  function addFinding(anchorKind, path, parent) {
    if (findings.length >= PR101_ARTIFACT_SHAPE_MAX_FINDINGS) return;
    const parentKeys = _pr101ShapeParentKeys(parent);
    const finding = {
      anchorKind,
      path: _pr101ShapePath(path),
      parentKeys
    };
    const fingerprint = `${finding.anchorKind}|${finding.path}|${finding.parentKeys.join(",")}`;
    if (!findings.some((item) => item.fingerprint === fingerprint)) {
      findings.push({ ...finding, fingerprint });
    }
  }

  function visit(value, path = [], depth = 0) {
    if (value == null || depth > PR101_ARTIFACT_SHAPE_MAX_DEPTH) return;
    if (budget.nodes >= PR101_ARTIFACT_SHAPE_MAX_NODES) return;
    budget.nodes += 1;

    if (Array.isArray(value)) {
      for (const item of value.slice(0, 128)) {
        if (findings.length >= PR101_ARTIFACT_SHAPE_MAX_FINDINGS) break;
        const anchorKind = _pr101ShapeAnchorKind(item);
        if (anchorKind) addFinding(anchorKind, [...path, "[]"], value);
        const parsed = _pr101ShapeMaybeParseJsonString(item);
        if (parsed) visit(parsed, [...path, "[]:json"], depth + 1);
        else if (item && typeof item === "object") visit(item, [...path, "[]"], depth + 1);
      }
      return;
    }

    if (typeof value !== "object" || _pr101ShapePrivateOrPromptObject(value)) return;
    for (const key of Object.keys(value).slice(0, PR101_ARTIFACT_SHAPE_MAX_KEYS)) {
      if (findings.length >= PR101_ARTIFACT_SHAPE_MAX_FINDINGS) break;
      const safeKey = _pr101ShapeSafeKey(key);
      if (!safeKey) continue;
      const child = value[key];
      const childPath = [...path, safeKey];
      const anchorKind = _pr101ShapeAnchorKind(child);
      if (anchorKind) addFinding(anchorKind, childPath, value);

      const parsed = _pr101ShapeMaybeParseJsonString(child);
      if (parsed) visit(parsed, [...childPath, ":json"], depth + 1);
      else if (child && typeof child === "object") visit(child, childPath, depth + 1);
    }
  }

  visit(root);
  return findings.map(({ fingerprint: _fingerprint, ...finding }) => finding);
}

function _pr101ShapeSummary(finding) {
  const keys = finding.parentKeys.length ? finding.parentKeys.join(",") : "none";
  return `anchor:${finding.anchorKind};path:${finding.path || "root"};keys:${keys}`.slice(0, 1200);
}

function _pr101ShapeState(context) {
  let state = _pr101ShapeEmissionState.get(context);
  if (state) return state;
  state = new Set();
  _pr101ShapeEmissionState.set(context, state);
  return state;
}

function _pr101ShapePayloadFromSseBlock(block) {
  let data = "";
  try {
    const dataLines = String(block || "").split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart());
    data = dataLines.join("\n").trim();
  } catch {
    return null;
  }
  if (!data || data === "[DONE]") return null;
  try {
    const payload = JSON.parse(data);
    return payload && typeof payload === "object" ? payload : null;
  } catch {
    return null;
  }
}

_pr89BrowserStreamProcessSseEvent = async function _pr101ArtifactShapeProcessSseEvent(context, block) {
  const result = await _pr101ShapePriorProcessSseEvent(context, block);
  if (_pr812RequestId === null) return result;

  try {
    const payload = _pr101ShapePayloadFromSseBlock(block);
    if (!payload) return result;
    const emitted = _pr101ShapeState(context);
    for (const finding of _pr101ShapeFindings(payload)) {
      const summary = _pr101ShapeSummary(finding);
      if (emitted.has(summary)) continue;
      emitted.add(summary);
      _pr812Emit(context, {
        type: PR101_ARTIFACT_SHAPE_EVENT,
        observation_id: `pr10.1:artifact-shape:${emitted.size}`,
        operation: "probe_filename_anchor",
        source_content_type: summary
      });
    }
  } catch {
    // Structural characterization is evidence-only and may never perturb a turn.
  }
  return result;
};

executeNativeTurn = async function _pr101ArtifactShapeSupportOverlay(message) {
  if (message?.characterizeGeneratedArtifactShapeSupport === true) {
    return {
      request_id: message.request_id,
      ok: true,
      generatedArtifactShapeCharacterizationSupported: true,
      generatedArtifactShapeCharacterizationSchemaVersion: PR101_ARTIFACT_SHAPE_SCHEMA_VERSION,
      probeFilenameAnchored: true,
      rawPayloadExported: false,
      artifactLocatorExported: false,
      writePerformed: false
    };
  }
  return _pr101ShapePriorExecuteNativeTurn(message);
};
