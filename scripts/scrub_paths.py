"""Make the deposited run records machine-neutral before release.

1. Folder paths recorded in transcripts (the files the agent's tools were given) become placeholders
   such as <BATS_DIR>, <DERIVED_DIR> or <TMP>. A path matches with or without its drive letter, since
   agent code that slices a path string can drop it (":\\Users\\..."), and with single or doubled
   separators.
2. A tool result that lists the process environment (the repr of os.environ, or a string that names
   three or more environment variables) is replaced by a one-line note, since such a listing names
   the machine and may carry session tokens.

JSON files are edited as parsed data (every string value), so escaping cannot break them; .md and
.csv files as text. Idempotent.

    python scripts/scrub_paths.py results "C:\\Users\\me\\data\\bats_v1.0=<BATS_DIR>" ...
"""
import json
import re
import sys
from pathlib import Path

ENV_KEYS = re.compile(r"'(USERNAME|USERPROFILE|COMPUTERNAME|HOMEPATH|HOMEDRIVE|HOME|USER|CLIENTNAME|PATH|"
                      r"APPDATA|LOCALAPPDATA|SYSTEMROOT|WINDIR|TEMP|TMP|TMPDIR|"
                      r"[A-Z_]*TOKEN[A-Z_]*|[A-Z_]*API_KEY[A-Z_]*)'\s*:")
ENV_NOTE = "[output removed before deposit: it listed the process environment]"


def _component(c: str) -> str:
    """Regex of one path component; a drive (C:) may appear without its letter (:)."""
    if re.fullmatch(r"[A-Za-z]:", c):
        return rf"(?:{re.escape(c[0])}:|(?<![A-Za-z]):)"
    return re.escape(c)


def compile_map(pairs):
    rules = []
    for prefix, placeholder in sorted(pairs, key=lambda kv: -len(kv[0])):      # most specific first
        comps = [c for c in re.split(r"[\\/]+", prefix) if c]
        rules.append((re.compile(r"[\\/]+".join(_component(c) for c in comps), re.I), placeholder))
    return rules


def is_environment(s: str) -> bool:
    """True for a listing of the process environment."""
    return "environ({" in s or len(ENV_KEYS.findall(s)) >= 3


def _clean(s: str, rules) -> tuple[str, int]:
    if is_environment(s):
        return ENV_NOTE, 1
    n = 0
    for rx, ph in rules:
        s, k = rx.subn(lambda m, ph=ph: ph, s)
        n += k
    return s, n


def _walk(obj, rules, count):
    if isinstance(obj, str):
        new, n = _clean(obj, rules)
        count[0] += n
        return new
    if isinstance(obj, list):
        return [_walk(x, rules, count) for x in obj]
    if isinstance(obj, dict):
        return {k: _walk(v, rules, count) for k, v in obj.items()}
    return obj


def scrub(root: Path, pairs) -> dict:
    rules = compile_map(pairs)
    changed = total = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            count = [0]
            new = _walk(data, rules, count)
            if count[0]:
                p.write_text(json.dumps(new, indent=1), encoding="utf-8")
                changed += 1
                total += count[0]
        elif p.suffix in (".md", ".csv", ".txt"):
            text = p.read_text(encoding="utf-8")
            new, n = _clean(text, rules) if not is_environment(text) else (text, 0)
            if n:
                p.write_text(new, encoding="utf-8")
                changed += 1
                total += n
    return {"files_changed": changed, "replacements": total}


if __name__ == "__main__":
    print(scrub(Path(sys.argv[1]), [tuple(a.split("=", 1)) for a in sys.argv[2:]]))
