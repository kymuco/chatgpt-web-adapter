// PR12.0 stable production browser-runtime entrypoint.
//
// This file owns assembly only. It must not acquire Browser Authority, touch the
// DOM/CDP directly, submit, navigate, retry, interpret canonical finality, or
// wrap runtime handlers. Domain modules below preserve the reviewed ordering
// while making cross-domain ownership explicit.

importScripts("service_worker_runtime_tab_reconciliation.js");
importScripts("service_worker_runtime_tab_id.js");
importScripts("service_worker_runtime_write.js");
importScripts("service_worker_submit_authority.js");
importScripts("service_worker_stream_metadata.js");
importScripts("service_worker_runtime_tab_resolution.js");
importScripts("service_worker_runtime_read.js");
importScripts("service_worker_runtime_observation.js");
importScripts("service_worker_deepseek_provider.js");
importScripts("service_worker_gemini_provider.js");
importScripts("service_worker_gemini_notebook_capability.js");
importScripts("service_worker_google_translate_capability.js");
importScripts("service_worker_native_message_router.js");
importScripts("service_worker_official_page_turn_lifecycle.js");
importScripts("service_worker_native_turn_lifecycle.js");
