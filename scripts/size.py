#!/usr/bin/env python3
"""Size a task spec with elephant-9b via OpenRouter Decisions (stdlib only).

Reads OPENROUTER_API_KEY from ~/.hermes/.env (never prints it). POSTs
{model, state, questions} to https://open-router.ai/api/alpha/decisions and
prints the decision JSON plus the router-ready size. Exit 0 = sized,
2 = clarify/spec_too_long, 1 = transport/schema error.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
MODEL_DEFAULT = "baseten/elephant-1"
MAX_SPEC_CHARS = 48000  # ~12k tokens; elephant caps at 16k total

SIZE_CRITERIA = {
    "S": "single-section doc edit, single script fix, or one obvious change",
    "M": "multi-step change across a few files, or verification + council work",
    "L": "multi-file feature, new logic, or 8+ files touched",
    "XL": "cross-cutting rework, infra migration, or deep redesign",
}
LEVELS = ["none", "low", "medium", "high"]


def load_key():
    for line in open(os.path.expanduser("~/.hermes/.env"), errors="replace"):
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY"):
            _, _, v = line.partition("=")
            v = v.strip().strip("\"'")
            if v:
                return v
    return ""


def decide(model, key, state, questions):
    body = json.dumps({"model": model, "state": state, "questions": questions}).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def main():
    p = argparse.ArgumentParser(description="size a spec with elephant-9b")
    p.add_argument("--spec", required=True)
    p.add_argument("--model", default=MODEL_DEFAULT)
    p.add_argument("--log", default="")
    p.add_argument("--jev-vague", type=float, default=None,
                   help="Jev yes-probability the spec is too vague (combines with elephant)")
    p.add_argument("--jev-size", default="",
                   help="Jev Choice size (tiebreak only)")
    p.add_argument("--jev-conf", type=float, default=0.0)
    p.add_argument("--theta", type=float, default=1.65,
                   help="risk bump threshold on the 0-3 score scale (elephant-fitted 1.65; Jev uses 1.85)")
    a = p.parse_args()
    key = load_key()
    if not key:
        print(json.dumps({"action": "error", "why": "no OPENROUTER_API_KEY"}))
        return 1
    with open(a.spec, errors="replace") as f:
        spec = f.read()
    if len(spec) > MAX_SPEC_CHARS:
        print(json.dumps({"action": "spec_too_long"}))
        return 2
    questions = {
        "size": {"type": "choice", "instructions": "What size is this task?",
                 "criteria": SIZE_CRITERIA},
        "risk": {"type": "score", "instructions": "How risky is this change?",
                 "criteria": LEVELS},
        "ambiguity": {"type": "score", "instructions": "How ambiguous is what to do?",
                       "criteria": LEVELS},
        "touch": {"type": "score", "instructions": "How many files or modules does it touch?",
                  "criteria": LEVELS},
        "tests_missing": {"type": "score",
                            "instructions": "How much is verification missing?",
                            "criteria": LEVELS},
        "vague": {"type": "noul",
                  "instructions": "Is this spec too vague to size?"},
    }
    try:
        raw = decide(a.model, key, spec, questions)
    except Exception as e:
        print(json.dumps({"action": "error", "why": "transport: %s" % str(e)[:200]}))
        return 1
    if a.log:
        d = os.path.dirname(a.log)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(a.log, "a") as f:
            f.write(json.dumps({"engine": "elephant-9b", "model": a.model,
                                "spec_sha256": hashlib.sha256(spec.encode()).hexdigest()[:16],
                                "raw": raw}) + "\n")
    ans = raw.get("answers", {}) or {}
    size = (ans.get("size", {}) or {}).get("choice")
    conf = round(float((ans.get("size", {}) or {}).get("confidence", 0.0)), 3)
    ev = float((ans.get("vague", {}) or {}).get("noul", 0.0))
    gr = float((ans.get("risk", {}) or {}).get("score", 0.0))
    out = {"engine": "elephant-9b", "model": a.model,
           "spec_sha256": hashlib.sha256(spec.encode()).hexdigest()[:16],
           "size": size, "size_confidence": conf, "vague_elephant": round(ev, 3),
           "raw": raw}
    jv = float(a.jev_vague or 0.0)
    vague = round(max(ev, jv), 3)
    out["vague_combined"] = vague
    if a.jev_vague is not None or a.jev_size:
        out["engine"] = "elephant-9b+jev"
        out["vague_jev"] = jv
        if jv and a.jev_size and a.jev_size != size and conf < 0.6:
            out["size"] = a.jev_size
            out["tiebreak"] = "jev (elephant confidence < 0.6)"
    if vague >= 0.5:
        out["action"] = "clarify"
        out["ask"] = ["goal in one line", "files/area touched",
                       "done = which tests"]
        print(json.dumps(out, indent=2))
        return 2
        if vague >= 0.2 or conf < 0.6:
            out["warnings"] = ["sizing_uncertain"] + (
                ["human glance advised (L/XL)"] if size in ("L", "XL") else [])
    final, bumped = size, False
    if final in ("S", "M", "L") and gr >= a.theta:
        final = {"S": "M", "M": "L", "L": "XL"}[final]
        bumped = True
    out["final_size"] = final
    out["bumped"] = bumped
    out["theta"] = a.theta
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
