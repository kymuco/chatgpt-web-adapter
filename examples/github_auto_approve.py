from __future__ import annotations

from webchat_adapter import ChatConversation, ChatGPTWebClient


REPO_SLUG = "your-user-or-org/your-repo"
BRANCH_NAME = "main"


def print_event(event: dict) -> None:
    event_type = event.get("type", "event")
    if event_type == "assistant_token":
        return
    print(f"[event] {event_type}: {event}")


def print_token(token: str) -> None:
    print(token, end="", flush=True)


def main() -> None:
    client = ChatGPTWebClient(auth_file="auth_data.json", timeout=120)

    prompt = f"""
Use the GitHub connector on repository {REPO_SLUG} on branch {BRANCH_NAME}.
Create exactly three separate text files as three separate tool actions, one file per action, in this exact order:
1. project-outline.txt with exact content: project outline draft
2. release-notes.txt with exact content: release notes draft
3. deployment-checklist.txt with exact content: deployment checklist draft
Do not modify any other files.
After each tool action completes, continue to the next file until all three files are created.
""".strip()

    response = client.send_and_auto_approve(
        prompt,
        model="gpt-5-5-thinking",
        reasoning_effort="extended",
        pending_poll_interval=3.0,
        settle_delay=2.0,
        max_rounds=0,
        on_token=print_token,
        on_event=print_event,
    )

    print()
    print("new chat result")
    print("conversation_id:", response.conversation.conversation_id)
    print("message_id:", response.conversation.message_id)
    print(response.text)

    follow_up = client.send_and_auto_approve(
        "Create one more file named handoff-notes.txt with exact content: handoff notes draft.",
        conversation=ChatConversation(conversation_id=response.conversation.conversation_id),
        model="gpt-5-5-thinking",
        reasoning_effort="extended",
        pending_poll_interval=3.0,
        settle_delay=2.0,
        max_rounds=0,
        on_token=print_token,
        on_event=print_event,
    )

    print()
    print("existing chat result")
    print("conversation_id:", follow_up.conversation.conversation_id)
    print("message_id:", follow_up.conversation.message_id)
    print(follow_up.text)


if __name__ == "__main__":
    main()
