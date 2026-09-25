// PR12.0 write-domain assembly.
//
// Preserve the reviewed rich-input ordering, then install bounded request-text
// shape compatibility, bounded browser-composer indentation compatibility,
// shared UI discovery, the ordinary-text protected commit boundary, and finally
// the request-bound ordinary-text conversation-identity authority. Read/
// observation modules are deliberately excluded from this domain.
//
// PR14.8 installs saved-conversation tab routing before rich-input wrappers so
// those wrappers preserve their deadline/cleanup semantics around the retained
// tab acquisition path.

importScripts("service_worker_retained_conversation_tabs.js");
importScripts("service_worker_rich_input_pr9_2.js");
importScripts("service_worker_rich_input_deadline_repair_pr9_2.js");
importScripts("service_worker_rich_input_closure_repair_pr9_2.js");
importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");
importScripts("service_worker_protected_submit_expression.js");
importScripts("service_worker_attachment_evidence.js");
importScripts("service_worker_attachment_cleanup.js");
importScripts("service_worker_attachment_staging.js");
importScripts("service_worker_rich_input_lifecycle.js");
importScripts("service_worker_request_text_shape_compat.js");
importScripts("service_worker_browser_indent_compat.js");
importScripts("service_worker_ui_compat_pr11_7.js");
importScripts("service_worker_text_submit_commit_hardening_pr11_3.js");
importScripts("service_worker_ordinary_text_identity_authority.js");
