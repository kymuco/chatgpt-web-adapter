// PR12.0 observation-domain assembly.
//
// Connector characterization registers explicit no-write diagnostic handlers;
// UI liveness wraps only Native Messaging observation after that surface is
// assembled and grants no write, retry, or canonical-finality authority.

importScripts("service_worker_connector_support_pr10_0.js");
importScripts("service_worker_ui_liveness.js");
