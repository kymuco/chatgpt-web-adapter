// PR12.0 compatibility bootstrap.
//
// Keep the historical manifest service-worker filename stable for existing
// extension packaging/tests, but move all product assembly into the explicit
// browser runtime root. The Temporary route-reopen implementation itself lives
// in the legacy domain loaded by service_worker_runtime.js.
//
// Historical topology reference only; PR12.0 moved this executable import into
// service_worker_runtime_write.js:
// importScripts("service_worker_rich_input_pr9_2.js")

importScripts("service_worker_runtime.js");
