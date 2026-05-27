from __future__ import annotations

from webchat_adapter import ChatConversation, ChatGPTWebClient


def main() -> None:
    client = ChatGPTWebClient(auth_file="auth_data.json", timeout=120)

    prompt = """
Use the GitHub connector on repository rn7-coder/new_repo on branch main.
Create exactly three separate text files as three separate tool actions, one file per action, in this exact order:
1. sdk-gh-case-1.txt with exact content: sdk case 1
2. sdk-gh-case-2.txt with exact content: sdk case 2
3. sdk-gh-case-3.txt with exact content: sdk case 3
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
        stop_when=lambda item: "created all three files" in item.text.lower(),
    )

    print("new chat result")
    print("conversation_id:", response.conversation.conversation_id)
    print("message_id:", response.conversation.message_id)
    print(response.text)

    follow_up = client.send_and_auto_approve(
        "Create one more file named sdk-gh-case-4.txt with exact content: sdk case 4.",
        conversation=ChatConversation(conversation_id=response.conversation.conversation_id),
        model="gpt-5-5-thinking",
        reasoning_effort="extended",
        pending_poll_interval=3.0,
        settle_delay=2.0,
        max_rounds=0,
        stop_when=lambda item: "sdk-gh-case-4.txt" in item.text,
    )

    print()
    print("existing chat result")
    print("conversation_id:", follow_up.conversation.conversation_id)
    print("message_id:", follow_up.conversation.message_id)
    print(follow_up.text)


if __name__ == "__main__":
    main()
