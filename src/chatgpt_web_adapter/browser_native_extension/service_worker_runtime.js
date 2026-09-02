// PR12.0 stable production browser-runtime entrypoint.
//
// This file owns assembly only. It must not acquire Browser Authority, touch the
// DOM/CDP directly, submit, navigate, retry, interpret canonical finality, or
// wrap runtime handlers. Domain modules below preserve the reviewed ordering
// while making cross-domain ownership explicit.

importScripts("service_worker_runtime_legacy.js");
importScripts("service_worker_runtime_write.js");
importScripts("service_worker_runtime_read.js");
importScripts("service_worker_runtime_observation.js");
