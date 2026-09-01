// PR10.1: bounded observation of product-generated downloadable artifacts.
//
// Artifact evidence requires an explicit product-owned artifact/file/asset id. This
// layer never invents identity from message order, filenames, URLs, DOM position, or
// assistant text. Download locators may be used only as an internal boolean signal
// that an explicitly identified artifact is downloadable; locator values never leave
// the worker in a turn_event.

const PR101_ARTIFACT_EVENT = "product_artifact_observed";
const _pr101PriorInspectMessage = _pr812InspectMessage;
const _pr101EmissionState = new WeakMap();

const _pr101ArtifactContainers = ["artifact", "file", "attachment", "asset", "generated_file"];
const _pr101ArtifactIdKeys = ["artifact_id", "file_id", "asset_id", "generated_file_id"];
const _pr101FilenameKeys = ["filename", "file_name"];
const _pr101MediaTypeKeys = ["media_type", "mime_type"];
const _pr101SizeKeys = ["size_bytes", "bytes", "file_size"];
const _pr101LocatorKeys = ["download_url", "download_uri", "signed_url", "url", "href"];

function _pr101OwnObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function _pr101OptionalString(value) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return text || null;
}

function _pr101SafeArtifactId(value) {
  const text = _pr101OptionalString(value);
  if (!text || text.length > 192 || !/^[A-Za-z0-9_.:-]+$/.test(text)) return null;
  const lower = text.toLowerCase();
  if (
    lower.includes("token") || lower.includes("secret") ||
    lower.includes("credential") || lower.includes("authorization") ||
    lower.includes("cookie")
  ) return null;
  return text;
}

function _pr101SafeFilename(value) {
  const text = _pr101OptionalString(value);
  if (!text || text.length > 255 || text === "." || text === "..") return null;
  if (/[\\/\u0000-\u001f]/.test(text)) return null;
  return text;
}

function _pr101SafeMediaType(value) {
  const text = _pr101OptionalString(value);
  if (!text) return null;
  const normalized = text.toLowerCase();
  if (normalized.length > 128) return null;
  if (!/^[A-Za-z0-9!#$&^_.+-]+\/[A-Za-z0-9!#$&^_.+-]+$/.test(normalized)) return null;
  return normalized;
}

function _pr101SafeSize(value) {
  return Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function _pr101FirstValue(object, keys) {
  if (!object) return null;
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(object, key) && object[key] != null) {
      return object[key];
    }
  }
  return null;
}

function _pr101HasLocator(object) {
  if (!object) return false;
  return _pr101LocatorKeys.some((key) => {
    const value = object[key];
    return typeof value === "string" && value.trim().length > 0;
  });
}

function _pr101CandidateFromObject(object, sourceOrigin) {
  object = _pr101OwnObject(object);
  if (!object) return null;

  const nestedCandidates = [];
  for (const key of _pr101ArtifactContainers) {
    const nested = _pr101OwnObject(object[key]);
    if (nested) nestedCandidates.push(nested);
  }
  const candidates = [object, ...nestedCandidates];

  for (const candidate of candidates) {
    const artifactId = _pr101SafeArtifactId(
      _pr101FirstValue(candidate, _pr101ArtifactIdKeys) ||
      (candidate !== object ? candidate.id : null)
    );
    if (!artifactId) continue;

    const filename = _pr101SafeFilename(
      _pr101FirstValue(candidate, _pr101FilenameKeys) ||
      (candidate !== object ? candidate.name : null)
    );
    const mediaType = _pr101SafeMediaType(_pr101FirstValue(candidate, _pr101MediaTypeKeys));
    const sizeBytes = _pr101SafeSize(_pr101FirstValue(candidate, _pr101SizeKeys));
    const downloadAvailable = _pr101HasLocator(candidate) || _pr101HasLocator(object) ||
      candidate.downloadable === true || object.downloadable === true;

    return {
      artifactId,
      filename,
      mediaType,
      sizeBytes,
      downloadAvailable,
      sourceOrigin
    };
  }
  return null;
}

function _pr101Candidates(message) {
  const output = [];
  const metadata = _pr101OwnObject(message?.metadata);
  const metadataCandidate = _pr101CandidateFromObject(metadata, "product_message_metadata");
  if (metadataCandidate) output.push(metadataCandidate);

  const content = _pr101OwnObject(message?.content);
  const parts = Array.isArray(content?.parts) ? content.parts.slice(0, 64) : [];
  for (const part of parts) {
    if (typeof part === "string") continue;
    const candidate = _pr101CandidateFromObject(part, "product_content_part");
    if (candidate) output.push(candidate);
  }

  const unique = new Map();
  for (const candidate of output) {
    if (!unique.has(candidate.artifactId)) unique.set(candidate.artifactId, candidate);
  }
  return Array.from(unique.values());
}

function _pr101State(state) {
  let local = _pr101EmissionState.get(state);
  if (local) return local;
  local = new Set();
  _pr101EmissionState.set(state, local);
  return local;
}

function _pr101InspectMessage(context, state, message) {
  if (!message || typeof message !== "object") return;
  if (message?.metadata?.is_visually_hidden_from_conversation === true) return;

  const messageId = _pr101SafeArtifactId(message.id) || "no-message";
  const emitted = _pr101State(state);
  for (const artifact of _pr101Candidates(message)) {
    const observationId = `pr10.1:${PR101_ARTIFACT_EVENT}:${artifact.artifactId}:${messageId}`;
    if (emitted.has(observationId)) continue;
    emitted.add(observationId);
    _pr812Emit(context, {
      type: PR101_ARTIFACT_EVENT,
      observation_id: observationId,
      artifact_id: artifact.artifactId,
      filename: artifact.filename,
      media_type: artifact.mediaType,
      size_bytes: artifact.sizeBytes,
      download_available: artifact.downloadAvailable,
      source_origin: artifact.sourceOrigin
    });
  }
}

_pr812InspectMessage = function _pr101GeneratedArtifactObservationOverlay(context, state, message) {
  _pr101PriorInspectMessage(context, state, message);
  try {
    _pr101InspectMessage(context, state, message);
  } catch {
    // Generated-artifact observation is evidence-only and may never perturb a turn.
  }
};
