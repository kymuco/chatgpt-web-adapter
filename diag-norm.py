from chatgpt_web_adapter.final_review_transport import _normalize_product_text as n
import json, glob, os, re

jp = sorted(glob.glob(r"C:\Users\Admin\.soc-brain\state\sessions\cwa-final-review\*.json"), key=lambda p: os.path.getmtime(p), reverse=True)[0]
j = json.load(open(jp, encoding="utf-8"))
from chatgpt_web_adapter import assemble_product_runtime, ConversationRef
rt = assemble_product_runtime()
msgs = rt.get_messages(ConversationRef(j["conversationId"]))
items = [m.to_dict() if hasattr(m, "to_dict") else m for m in msgs]
user = [m for m in items if m.get("role") == "user"][0]
np = n(j["payloadText"])
nl = n(user.get("text"))
out = []
if nl == np:
    out.append("EQUAL")
else:
    out.append(f"len np {len(np)} nl {len(nl)}")
    diffs = 0
    for i, (x, y) in enumerate(zip(np, nl)):
        if x != y:
            diffs += 1
            if diffs <= 5:
                out.append(f"diff {i}: np={repr(np[max(0,i-25):i+25])} nl={repr(nl[max(0,i-25):i+25])}")
    if len(np) != len(nl):
        out.append(f"tail np={repr(np[min(len(np),len(nl)):][:120])}")
        out.append(f"tail nl={repr(nl[min(len(np),len(nl)):][:120])}")
open(r"C:\Users\Admin\.soc-brain\dev\diff-out.txt", "w", encoding="utf-8").write("\n".join(out))
print("written")
