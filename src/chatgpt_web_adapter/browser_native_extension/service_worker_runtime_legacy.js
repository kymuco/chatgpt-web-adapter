// PR12.0 legacy-domain assembly.
//
// Historical PR8 runtime behavior remains in its reviewed implementation, now
// behind an explicit domain boundary. The historical manifest filename is only
// a compatibility bootstrap into service_worker_runtime.js.

importScripts("service_worker_runtime_legacy_impl.js");
