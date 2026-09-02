// PR9.2 schema compatibility loader.
//
// Keep the historical entrypoint import stable while preserving reviewed schema
// generations as immutable layers. PR9.2 schema 29 remains the final rich-input
// authority layer; PR11.3 may harden only the text-only submit boundary after it,
// while later product-observation/read overlays do not acquire write authority.
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

// PR11.3 text-only write-boundary hardening. This layer delegates active rich
// contexts to the complete PR9.2 chain above and only removes post-mouse-release
// fallback/retry authority from ordinary text submission.
importScripts("service_worker_text_submit_commit_hardening_pr11_3.js");

// PR9.3 observational-only source/citation normalization. Loaded after the final
// write-authority layers so it can observe PR8.12 message events without
// participating in attachment staging, protected submit, retry, or finality.
importScripts("service_worker_product_source_citations_pr9_3.js");

// PR11.2 canonical reads are an observation/read overlay only. Load them after
// the final write-authority generations and PR9.3 observation layer, while
// leaving the historical manifest and PR10.0 outer executeNativeTurn wrapper intact.
importScripts("service_worker_canonical_read.js");