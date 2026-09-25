from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
OWNER = "service_worker_official_page_turn_lifecycle.js"

FORMER_OWNERS = (
    "service_worker_observability_page_turn_lifecycle.js",
    "service_worker_temporary_product.js",
    "service_worker_rich_input_pr9_2.js",
    "service_worker_rich_input_schema16_repair_pr9_2.js",
    "service_worker_rich_input_schema17_repair_pr9_2.js",
    "service_worker_rich_input_schema18_repair_pr9_2.js",
    "service_worker_rich_input_schema19_repair_pr9_2.js",
    "service_worker_rich_input_schema20_repair_pr9_2.js",
    "service_worker_rich_input_schema29_repair_pr9_2.js",
    "service_worker_ordinary_text_identity_authority.js",
)


def _source(name: str) -> str:
    return (EXT / name).read_text(encoding="utf-8")


def _run_node(script: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_former_page_turn_owners_are_pure() -> None:
    for name in FORMER_OWNERS:
        source = _source(name)
        assert "executeOfficialPageTurn =" not in source, name
        assert "= executeOfficialPageTurn;" not in source, name


def test_runtime_loads_single_page_turn_owner_before_native_turn_owner() -> None:
    runtime = _source("service_worker_runtime.js")
    page = 'importScripts("service_worker_official_page_turn_lifecycle.js");'
    native = 'importScripts("service_worker_native_turn_lifecycle.js");'

    assert page in runtime and native in runtime
    assert runtime.index(page) < runtime.index(native)

    owner = _source(OWNER)
    assert owner.count("async function executeOfficialPageTurn(") == 1
    assert "executeOfficialPageTurn =" not in owner


def test_page_turn_graph_exposes_intentional_bypass_edges() -> None:
    owner = _source(OWNER)

    assert "_cwaOfficialPageTurnSchema18" in owner
    assert "_cwaOfficialPageTurnSchema17" in owner
    assert "_cwaOfficialPageTurnSchema20" in owner
    assert "_cwaOfficialPageTurnSchema19" in owner

    schema19 = owner[
        owner.index("async function _cwaOfficialPageTurnSchema19") : owner.index(
            "async function _cwaOfficialPageTurnSchema20"
        )
    ]
    assert "_cwaOfficialPageTurnSchema18" in schema19
    assert "_cwaOfficialPageTurnSchema17" in schema19

    schema29 = owner[
        owner.index("async function _cwaOfficialPageTurnSchema29") : owner.index(
            "async function _cwaOfficialPageTurnOrdinaryIdentity"
        )
    ]
    assert "_cwaOfficialPageTurnSchema20" in schema29
    assert "_cwaOfficialPageTurnSchema19" in schema29


def test_page_turn_graph_preserves_normal_and_bypass_routes() -> None:
    owner = _source(OWNER)
    script = f"""
const calls = [];

function linear(name) {{
  return async (args, next) => {{
    calls.push(name);
    return next(args);
  }};
}}

async function _executeOfficialPageTurnWithObservabilityLifecycle(args) {{
  calls.push("observability");
  return {{ mode: args.mode }};
}}

const _pr813ExecuteOfficialPageTurnWithSessionIdentity = linear("temporary");
const _pr92ExecuteOfficialPageTurnWithinTurn = linear("rich");
const _pr92Schema16ExecuteOfficialPageTurnWithinTurn = linear("schema16");
const _pr92Schema17ExecuteOfficialPageTurnWithinTurn = linear("schema17");
const _pr92Schema18ExecuteOfficialPageTurnWithIdentityAuthority = linear("schema18");

async function _pr92Schema19ExecuteOfficialPageTurnWithRequestBoundIdentity(
  args,
  next,
  bypassSchema18
) {{
  calls.push("schema19");
  return args.mode === "bypass18" ? bypassSchema18(args) : next(args);
}}

const _pr92Schema20ExecuteOfficialPageTurnWithSubmitBoundRequest = linear("schema20");

async function _pr92Schema29ExecuteOfficialPageTurn(args, next, bypassSchema20) {{
  calls.push("schema29");
  return args.mode === "bypass20" ? bypassSchema20(args) : next(args);
}}

const _cwaOrdinaryIdentityExecuteOfficialPageTurn = linear("ordinary");

{owner}

async function run(mode) {{
  calls.length = 0;
  await executeOfficialPageTurn({{ mode }});
  return [...calls];
}}

(async () => {{
  console.log(JSON.stringify({{
    normal: await run("normal"),
    bypass18: await run("bypass18"),
    bypass20: await run("bypass20")
  }}));
}})().catch((error) => {{
  console.error(error);
  process.exit(1);
}});
"""
    result = _run_node(script)

    assert result["normal"] == [
        "ordinary",
        "schema29",
        "schema20",
        "schema19",
        "schema18",
        "schema17",
        "schema16",
        "rich",
        "temporary",
        "observability",
    ]
    assert result["bypass18"] == [
        "ordinary",
        "schema29",
        "schema20",
        "schema19",
        "schema17",
        "schema16",
        "rich",
        "temporary",
        "observability",
    ]
    assert result["bypass20"] == [
        "ordinary",
        "schema29",
        "schema19",
        "schema18",
        "schema17",
        "schema16",
        "rich",
        "temporary",
        "observability",
    ]
