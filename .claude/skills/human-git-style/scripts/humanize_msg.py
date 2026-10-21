import re
import sys
import zlib

# מצב: full = מנקה חתימה + מקצר סגנון, trailer = רק מוחק את חתימת Claude
mode = sys.argv[1] if len(sys.argv) > 1 else "full"
raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")

lines = raw.splitlines()
keep = []
for line in lines:
    low = line.strip().lower()
    if low.startswith("co-authored-by:") and ("claude" in low or "anthropic" in low):
        continue
    if "generated with [claude code]" in low or "generated with claude code" in low:
        continue
    keep.append(line)

while keep and not keep[-1].strip():
    keep.pop()

if mode == "trailer":
    out = "\n".join(keep)
else:
    subject = keep[0].strip() if keep else "update"
    m = re.match(r"^chore:\s*merge executor worktree.*$", subject, re.I)
    if m:
        subject = "merge"
    else:
        # מוריד prefix בסגנון feat(11-04): / docs(phase-11):
        subject = re.sub(r"^[a-z]+(\([^)]*\))?!?:\s*", "", subject, flags=re.I)
        subject = subject.replace(" — ", " - ").replace("—", "-")
        subject = subject.rstrip(".").strip()
        if subject:
            # רוב ההודעות באותיות קטנות, חלק נשארות עם אות גדולה
            h = zlib.crc32(subject.encode("utf-8")) % 100
            if h >= 15:
                subject = subject[0].lower() + subject[1:]
            else:
                subject = subject[0].upper() + subject[1:]
        else:
            subject = "update"
    out = subject

sys.stdout.buffer.write((out + "\n").encode("utf-8"))
