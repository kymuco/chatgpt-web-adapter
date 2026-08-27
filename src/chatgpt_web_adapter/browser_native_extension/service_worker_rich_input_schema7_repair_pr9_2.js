// PR9.2 schema compatibility loader.
//
// Keep the historical entrypoint import stable while preserving reviewed schema
// generations as immutable layers. The newest closure repair is loaded last.
importScripts("service_worker_rich_input_schema7_core_pr9_2.js");
importScripts("service_worker_rich_input_schema8_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema9_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema10_repair_pr9_2.js");
