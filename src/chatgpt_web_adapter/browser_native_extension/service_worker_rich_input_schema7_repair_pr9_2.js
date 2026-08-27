// PR9.2 schema-7 compatibility loader.
//
// Keep the historical entrypoint import stable while preserving the exact
// reviewed schema-7 implementation as an immutable core and loading the schema-8
// closure repair immediately after it.
importScripts("service_worker_rich_input_schema7_core_pr9_2.js");
importScripts("service_worker_rich_input_schema8_repair_pr9_2.js");
