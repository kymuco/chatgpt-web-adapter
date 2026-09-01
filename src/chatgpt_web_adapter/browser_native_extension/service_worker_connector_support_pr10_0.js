// PR10.0: outermost no-write connector observation support probe.
//
// The connector message-observation overlay is intentionally loaded inside the
// normalized activity stream, but PR9.2 rich-input wrappers are loaded later by
// the manifest entrypoint. A support characterization must therefore sit outside
// the complete production stack; otherwise an unknown no-write flag can be
// mistaken for an ordinary turn and enter rich-input preflight before reaching
// the connector handler.
//
// This wrapper never types, submits, stages attachments, acquires write authority,
// approves actions, changes canonical finality, retries, or selects a fallback.

const _pr100SupportPriorExecuteNativeTurn = executeNativeTurn;

executeNativeTurn = async function _pr100ExecuteNativeTurnWithOutermostSupportProbe(message) {
  if (message?.characterizeConnectorObservationSupport !== true) {
    return _pr100SupportPriorExecuteNativeTurn(message);
  }

  if (
    message?.text != null ||
    message?.conversationId != null ||
    message?.attachmentPaths != null ||
    message?.browserAuthorityLeaseId != null
  ) {
    throw new Error("PR10_0_CONNECTOR_SUPPORT_PROBE_MUST_BE_NO_WRITE");
  }

  return {
    connectorObservationSupported: true,
    connectorObservationSchemaVersion: PR100_CONNECTOR_OBSERVATION_SCHEMA,
    explicitConnectorIdentityRequired: true,
    explicitLifecycleCorrelationRequired: true,
    genericToolActivityImpliesConnector: false,
    rawConnectorPayloadExported: false,
    connectorObservationGrantsApprovalAuthority: false,
    connectorObservationChangesCanonicalFinality: false,
    connectorObservationChangesRetryAuthority: false,
    automaticWriteRetry: false,
    fallbackTransport: null,
    writePerformed: false
  };
};
