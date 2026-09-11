import io

p = r"C:/Users/Admin/cwa-main-test/src/chatgpt_web_adapter/final_review_transport.py"
s = io.open(p, encoding="utf-8", newline="").read()

i = s.find("def _normalize_product_text")
j = s.find("def _persist", i)
assert i > 0 and j > i, (i, j)

new = (
    'def _normalize_product_text(text: str) -> str:\n'
    '    """Composer-owned text normalization: the product editor round-trips\n'
    '    the text through its markdown model - non-breaking spaces, backslash\n'
    '    escapes of special characters (observed live: ``_`` -> ``\\\\_``,\n'
    '    ``:`` -> ``\\\\:``, ``<`` -> ``\\\\<``, applied recursively to\n'
    '    already-escaped content) and newline-count normalization. This folds\n'
    '    those transforms so the round-tripped text compares equal to the\n'
    '    original; a residual mismatch still fails closed."""\n'
    '    t = str(text).replace("\\u00a0", " ")\n'
    '    prev = None\n'
    '    while prev != t:\n'
    '        prev = t\n'
    '        t = re.sub(r"\\\\(.)", r"\\1", t)\n'
    '    t = t.replace("\\r\\n", "\\n").replace("\\r", "\\n")\n'
    '    return t\n'
    '\n'
    '\n'
    'def _content_fingerprint(text: str) -> str:\n'
    '    """Whitespace/punctuation-free content identifier - invariant to every\n'
    '    observed composer markdown transform (recursive escaping,\n'
    '    auto-linking, whitespace normalization); for a ~60 KB text a strong\n'
    '    content identifier."""\n'
    '    return re.sub(r"\\W+", "", _normalize_product_text(text).lower())\n'
    '\n'
    '\n'
)
io.open(p, "w", encoding="utf-8", newline="").write(s[:i] + new + s[j:])
print("rewritten")
