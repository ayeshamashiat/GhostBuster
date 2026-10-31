"""After you fill audit/output_audit.md: agreement between the automatic checker and your labels."""
import json
import re

key = json.load(open("audit/.key.json"))
MAP = {"correct": "C", "wrong": "W", "abstain": "N"}
n = agree = 0
conf = {}
for line in open("audit/output_audit.md", encoding="utf-8"):
    m = re.match(r"\|\s*(\d+)\s*\|.*\|\s*([CWNcwn])\s*\|\s*$", line)
    if not m:
        continue
    i, h = m.group(1), m.group(2).upper()
    a = MAP.get(key[i]["auto"], "?")
    n += 1
    agree += a == h
    conf[(a, h)] = conf.get((a, h), 0) + 1
print(f"labelled {n}/100; automatic checker agrees with you on {agree}/{n} = {100*agree/max(n,1):.0f}%")
for (a, h), c in sorted(conf.items()):
    print(f"  auto={a} human={h}: {c}")
