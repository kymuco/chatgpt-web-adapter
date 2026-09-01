// PR9.2 schema compatibility loader.
//
// Keep the historical entrypoint import stable while preserving reviewed schema
// generations as immutable layers. PR9.2 schema 29 remains the final rich-input
// authority layer; later product-observation overlays may load after it but do
// not acquire write authority.
importScripts("service_worker_rich_input_schema7_core_pr9_2.js");
importScripts("service_worker_rich_input_schema8_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema9_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema10_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema11_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema12_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema13_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema14_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema15_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema16_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema17_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema18_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema19_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema20_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema21_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema22_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema23_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema24_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema23_diagnostic_pr9_2.js");
importScripts("service_worker_rich_input_schema25_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema26_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema26_staging_diagnostic_pr9_2.js");
importScripts("service_worker_rich_input_schema27_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema27_staging_diagnostic_pr9_2.js");
importScripts("service_worker_rich_input_schema28_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema28_diagnostic_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema29_repair_pr9_2.js");

// PR9.3 observational-only source/citation normalization. Loaded after the final
// PR9.2 authority generation so it can observe PR8.12 message events without
// participating in attachment staging, protected submit, retry, or finality.
importScripts("service_worker_product_source_citations_pr9_3.js");
