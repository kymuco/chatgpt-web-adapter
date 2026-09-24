// PR15.28 explicit safe stream-metadata owner.
//
// Historical source-order composition was:
//
//   schema29 -> schema28 -> schema19 -> Instant -> base
//
// Keep that exact outer-to-inner call graph without import-time hook reassignment.

function extractSafeStreamMetadata(body, base64Encoded) {
  return _pr92Schema29ExtractSafeStreamMetadata(
    body,
    base64Encoded,
    (schema29Body, schema29Base64Encoded) =>
      _pr92Schema28ExtractSafeStreamMetadata(
        schema29Body,
        schema29Base64Encoded,
        (schema28Body, schema28Base64Encoded) =>
          _pr92Schema19ExtractRequestBoundStreamMetadata(
            schema28Body,
            schema28Base64Encoded,
            (schema19Body, schema19Base64Encoded) =>
              _pr88ExtractSafeStreamMetadataWithInstantHints(
                schema19Body,
                schema19Base64Encoded,
                _cwaBaseExtractSafeStreamMetadata
              )
          )
      )
  );
}
