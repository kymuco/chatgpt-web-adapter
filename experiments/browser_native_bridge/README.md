# Browser-native bridge probe

Research assets for `docs/browser_native_bridge_feasibility.md`.

Load the `extension/` directory as an unpacked Chrome extension. This probe is
not part of the packaged Python SDK and must not be treated as a supported
transport until the PR8.0 live kill-gates pass.

Current research actions:

- **Probe capabilities** — enumerate existing ChatGPT tabs and debugger state.
- **Send through official page** — execute one explicitly targeted official-page turn.
- **Run 20-turn background stress** — execute the fixed PR8.0b repeatability markers
  against one inactive ChatGPT tab and report safe transport diagnostics only.

After the stress action reports 20/20, run
`python examples/verify_browser_native_stress.py <conversation-id>` to verify the
canonical conversation through the existing SDK read path.
