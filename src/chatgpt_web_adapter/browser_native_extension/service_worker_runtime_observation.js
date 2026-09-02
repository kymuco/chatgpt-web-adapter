// PR12.0 observation-domain assembly.
//
// Connector characterization remains the terminal executeNativeTurn wrapper;
// UI liveness only wraps Native Messaging observation after that turn surface is
// assembled and grants no write, retry, or canonical-finality authority.

importScripts("service_worker_connector_support_pr10_0.js");
importScripts("service_worker_ui_liveness.js");
