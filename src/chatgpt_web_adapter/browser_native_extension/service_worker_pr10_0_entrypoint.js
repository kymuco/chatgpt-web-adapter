// PR10.0 manifest entrypoint.
//
// Assemble the complete released browser-owned production worker first, including
// the full PR9.2 rich-input stack. Only then install the PR10.0 no-write support
// characterization wrapper so that its flag cannot be mistaken for an ordinary
// product turn by an older outer layer.

importScripts("service_worker_temporary_chat_route_reopen_probe.js");
importScripts("service_worker_connector_support_pr10_0.js");
