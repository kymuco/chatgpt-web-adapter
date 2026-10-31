"""Primary ChatGPT Direct HTTP SDK example.

Prerequisites: a saved authenticated auth_data.json, Node.js 24+ and curl.
Initial interactive login can be done with:
    chatgpt-web-adapter auth login --auth-file auth_data.json
No Chrome tab is needed for subsequent Direct HTTP sending.
"""

from __future__ import annotations

import argparse

from chatgpt_web_adapter import BrowserlessHTTPClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one ChatGPT Direct HTTP turn")
    parser.add_argument("prompt", nargs="?", default="Explain CWA in two sentences.")
    parser.add_argument("--auth-file", default="auth_data.json")
    args = parser.parse_args()

    client = BrowserlessHTTPClient(auth_file=args.auth_file)
    response = client.send(args.prompt)
    print(response.text)


if __name__ == "__main__":
    main()
