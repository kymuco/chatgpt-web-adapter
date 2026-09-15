// PR12.0 write-domain assembly.
//
// Preserve the reviewed rich-input ordering, then install shared UI discovery,
// the ordinary-text protected commit boundary, request-bound conversation-identity
// authority, and finally the ordinary committed-error preservation boundary.
// Read/observation modules are deliberately excluded from this domain.

importScripts("service_worker_rich_input_pr9_2.js");
importScripts("service_worker_rich_input_deadline_repair_pr9_2.js");
importScripts("service_worker_rich_input_closure_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");
importScripts("service_worker_ui_compat_pr11_7.js");
importScripts("service_worker_text_submit_commit_hardening_pr11_3.js");
importScripts("service_worker_ordinary_text_identity_authority.js");
importScripts("service_worker_ordinary_text_identity_error_boundary.js");
