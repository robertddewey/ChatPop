#!/usr/bin/env python3
"""
build_allowlists.py

Auto-build ALLOWLIST_TOKENS and ALLOWLIST_SUBSTRINGS given:
- SHORT_RISKY: short obscene roots prone to false positives
- BANNED_WORDS: your hard blacklist (no spaces, lowercase)

Sources for English words:
1) wordfreq (if installed): high-quality, deduped words (frequency threshold configurable)
2) /usr/share/dict/words (if present)
3) small built-in fallback set

Usage:
  python build_allowlists.py --out-py allowlists.py
  python build_allowlists.py --out-json allowlists.json
  python build_allowlists.py --min-zipf 3.5 --min-length 3

Tips:
- Review the generated allowlists. If anything problematic appears, add it to
  EXCLUDE_TOKENS or EXCLUDE_SUBSTRINGS below (or keep it in BANNED_WORDS).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, Iterable, List, Set

from username_words import BANNED_WORDS, SHORT_RISKY

# -----------------------
# INPUTS (edit to taste)
# -----------------------

# Your short risky roots (expand as desired)
SHORT_RISKY: Set[str] = set(SHORT_RISKY)

# Import your real BANNED_WORDS set here (no spaces, lowercase).
# For production, replace with: from chats.username_words import BANNED_WORDS
BANNED_WORDS: Set[str] = set(BANNED_WORDS)

# Optional explicit exclusions if something slips through as allowlist
EXCLUDE_TOKENS: Set[str] = set(
    {
        # Example: if you keep "coc" risky, you probably don't want 'cocaine'
        # Remove any other problematic words that slip through
    }
)

EXCLUDE_SUBSTRINGS: Set[str] = set(
    {
        # Example substrings you never want to bless globally
        # (usually keep empty; rely on BANNED_WORDS)
    }
)

# -----------------------
# WORD SOURCING
# -----------------------

_WORD_RE = re.compile(r"^[a-z][a-z''-]*$")  # simple English-ish token


def load_wordfreq_words(min_zipf: float = 3.5) -> Set[str]:
    """
    Load words from 'wordfreq' if available.
    zipf_frequency scale: 1 (rare) .. 7 (very common). 3.5 ≈ moderate.
    """
    try:
        from wordfreq import top_n_list, zipf_frequency

        print("[info] Using wordfreq library for high-quality word list")
    except Exception:
        print("[info] wordfreq not available, falling back to system dictionary")
        return set()

    # Use a generous top list; filter again by zipf later
    raw = set(top_n_list("en", n_top=200000))  # ~200k common English tokens
    out = set()
    for w in raw:
        lw = w.lower()
        if _WORD_RE.match(lw) and zipf_frequency(lw, "en") >= min_zipf:
            out.add(lw)

    print(f"[info] Loaded {len(out)} words from wordfreq (min_zipf={min_zipf})")
    return out


def load_system_words(path: str = "/usr/share/dict/words") -> Set[str]:
    """Load words from system dictionary file"""
    out = set()
    if not os.path.exists(path):
        print(f"[info] System dictionary not found at {path}")
        return out

    print(f"[info] Loading words from system dictionary: {path}")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            w = line.strip().lower()
            if _WORD_RE.match(w):
                out.add(w)

    print(f"[info] Loaded {len(out)} words from system dictionary")
    return out


def fallback_words() -> Set[str]:
    """Fallback word list for when no external sources available"""
    print("[info] Using built-in fallback word list")
    return {
        # Words containing "ass"
        "pass",
        "password",
        "passenger",
        "compass",
        "class",
        "classroom",
        "glasses",
        "grass",
        "mass",
        "amass",
        "broadcast",
        "asset",
        "assets",
        "assess",
        "assessment",
        "assistant",
        "assist",
        "associate",
        "association",
        "assert",
        "assignment",
        "assembly",
        "assume",
        "assumption",
        "embarrass",
        "reassure",
        "harass",
        "brass",
        "bass",
        "lass",
        "lasso",
        "assassin",
        "classic",
        "classification",
        "classical",
        "massage",
        "passage",
        "message",
        "trespass",
        "surpass",
        "bypass",
        "underpass",
        "overpass",
        "jackass",
        "dumbass",
        "badass",
        "kickass",
        "smartass",
        "hardass",
        # Words containing "cum"
        "cumlaude",
        "cumulative",
        "accumulate",
        "accumulation",
        "accumulator",
        "cumin",
        "document",
        "documents",
        "documentary",
        "circumference",
        "circumstance",
        "cucumber",
        "succumb",
        "incumbent",
        "decorum",
        "curriculum",
        "vacuum",
        "summum",
        "maximum",
        "minimum",
        "premium",
        "momentum",
        "spectrum",
        "museum",
        # Words containing "tit"
        "title",
        "titles",
        "entitle",
        "entitled",
        "entitlement",
        "titan",
        "titanium",
        "constitution",
        "constitutional",
        "stitute",
        "institute",
        "substitute",
        "prostitute",
        "constitute",
        "destitute",
        "restitution",
        "superstition",
        "constitute",
        "stitched",
        "stitching",
        "appetite",
        "repetitive",
        "competitive",
        "partition",
        "petition",
        "position",
        "tradition",
        "condition",
        "addition",
        "audition",
        "tuition",
        "intuition",
        "nutrition",
        "ammunition",
        "definition",
        # Words containing "sex"
        "utility",
        "utilities",
        "legit",
        "partition",
        "stitched",
        "intersection",
        "sussex",
        "essex",
        "middlesex",
        "dyslexia",
        "asexual",
        "bisexual",
        "sexual",
        "sextet",
        "sextant",
        "sexuality",
        "sexism",
        "sexist",
        "unisex",
        "intersex",
        # Words containing "pen"
        "pen",
        "pencil",
        "pencils",
        "peninsula",
        "penal",
        "penalty",
        "penmanship",
        "open",
        "opened",
        "opening",
        "opener",
        "happen",
        "happened",
        "happening",
        "epen",
        "depend",
        "dependent",
        "independent",
        "suspend",
        "append",
        "expend",
        "spend",
        "spending",
        "expensive",
        "experience",
        "experiment",
        "expert",
        "carpenter",
        "serpent",
        "repent",
        "supplement",
        "implement",
        "complement",
        # Words containing "dic"
        "dictionary",
        "dictionaries",
        "diction",
        "dictation",
        "predict",
        "prediction",
        "indicative",
        "indicate",
        "indication",
        "verdict",
        "jurisdiction",
        "edict",
        "medical",
        "radical",
        "syndicate",
        "vindicate",
        "abdicate",
        "dedicate",
        "predicament",
        "predictor",
        "addicted",
        "addiction",
        "interdiction",
        "benediction",
        "malediction",
        "contradiction",
        "jurisdiction",
        "vindication",
        # Words containing "pus"
        "octopus",
        "octopi",
        "platypus",
        "corpus",
        "corpora",
        "campus",
        "campuses",
        "purpose",
        "purposes",
        "purposeful",
        "push",
        "pushed",
        "pushing",
        "pusher",
        "opus",
        "repugnant",
        "repulsive",
        "impulse",
        "propulsion",
        "expulsion",
        "compulsive",
        "compulsion",
        "repulsion",
        "pulsation",
        "pulse",
        "pulsar",
        # Words containing "coc"
        "cocoa",
        "coconut",
        "coconuts",
        "cocoon",
        "coccyx",
        "cocci",
        "precocious",
        "locomotive",
        "democracy",
        "democratic",
        "aristocrat",
        "autocrat",
        "theocracy",
        "bureaucracy",
        "meritocracy",
        "plutocracy",
        "technocracy",
        "protocol",
        # Words containing "fuc" (limited legitimate words)
        "confucian",
        "confucius",
        "fuchsia",
        "fuchs",
        "fuchsite",
        # Words containing other risky patterns
        "focus",
        "focused",
        "focusing",
        "focuses",
        "fuchsia",
        "confucian",
        "japan",
        "japanese",
        "japonica",
        "nippon",
        "snippet",
        "snippets",
        "turnip",
        "manila",
        "vanilla",
        "gorilla",
        "guerrilla",
        "thrilla",
        "villa",
        "pillar",
        "assassin",
        "passion",
        "compassion",
        "dispassionate",
        "impassive",
        "passive",
        "aggressive",
        "progressive",
        "regressive",
        "excessive",
        "successive",
        "impressive",
        "expressive",
        "oppressive",
        "depressive",
        "suppressive",
        "compressive",
        "massive",
        # General good words to include
        "amazing",
        "awesome",
        "beautiful",
        "brilliant",
        "creative",
        "excellent",
        "fantastic",
        "gorgeous",
        "incredible",
        "magnificent",
        "outstanding",
        "perfect",
        "spectacular",
        "stunning",
        "superb",
        "wonderful",
        "marvelous",
        "fabulous",
        "extraordinary",
        "remarkable",
        "impressive",
        "exceptional",
        "phenomenal",
        "breathtaking",
        "dazzling",
        "exquisite",
        "flawless",
        "glorious",
        "majestic",
        "splendid",
        "terrific",
        "tremendous",
        "unbelievable",
        "magnificent",
        "divine",
    }


def load_words(min_zipf: float) -> Set[str]:
    """Load words from best available source"""
    words = load_wordfreq_words(min_zipf=min_zipf)
    if not words:
        words = load_system_words()
    if not words:
        words = fallback_words()

    # normalize and filter
    words = {w.strip().lower() for w in words if w.strip()}
    words = {w for w in words if _WORD_RE.match(w)}

    print(f"[info] Final word set contains {len(words)} words")
    return words


# -----------------------
# ALLOWLIST BUILDERS
# -----------------------


def build_allowlist_tokens(
    words: Set[str],
    short_risky: Set[str],
    banned: Set[str],
    min_len: int = 3,
) -> Set[str]:
    """
    Whole-word allowlist: words that contain any short risky substring,
    but are not in banned list and meet basic length criteria.
    """
    print(f"[info] Building token allowlist from {len(words)} words...")

    out: Set[str] = set()
    sr = sorted(short_risky, key=len, reverse=True)

    risky_counts = {r: 0 for r in sr}

    for w in words:
        if len(w) < min_len:
            continue
        if w in banned or w in EXCLUDE_TOKENS:
            continue

        # Check if word contains any risky substring
        contains_risky = False
        for r in sr:
            if r in w:
                risky_counts[r] += 1
                contains_risky = True
                break  # Only count once per word

        if contains_risky:
            out.add(w)

    # Print statistics
    print(f"[info] Found {len(out)} legitimate words containing risky substrings:")
    for risky, count in sorted(risky_counts.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  '{risky}': {count} words")

    return out


def build_allowlist_substrings(
    allow_tokens: Set[str],
    short_risky: Set[str],
    min_hits: int = 20,
    max_sub_len: int = 6,
) -> Set[str]:
    """
    Heuristic: propose substrings for global allow if they appear across
    many allowlisted tokens (min_hits). Keeps substrings short-ish.
    Start with each SHORT_RISKY root and accept only if frequent in allow tokens.
    """
    print(f"[info] Building substring allowlist (min_hits={min_hits})...")

    counts: Dict[str, int] = {}
    examples: Dict[str, List[str]] = {}

    for root in short_risky:
        for w in allow_tokens:
            if root in w:
                counts[root] = counts.get(root, 0) + 1
                if root not in examples:
                    examples[root] = []
                if len(examples[root]) < 5:  # Keep a few examples
                    examples[root].append(w)

    candidates = {
        k for k, v in counts.items() if v >= min_hits and len(k) <= max_sub_len and k not in EXCLUDE_SUBSTRINGS
    }

    # Print statistics
    print(f"[info] Substring frequency analysis:")
    for sub, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        status = "✓ ALLOWED" if sub in candidates else "✗ rejected"
        reason = ""
        if sub in EXCLUDE_SUBSTRINGS:
            reason = "(explicitly excluded)"
        elif count < min_hits:
            reason = f"(< {min_hits} hits)"
        elif len(sub) > max_sub_len:
            reason = f"(> {max_sub_len} chars)"

        print(f"  '{sub}': {count:3d} hits {status} {reason}")
        if sub in examples and examples[sub]:
            example_str = ", ".join(examples[sub][:3])
            if len(examples[sub]) > 3:
                example_str += f" (+{len(examples[sub])-3} more)"
            print(f"    Examples: {example_str}")

    return candidates


# -----------------------
# SERIALIZERS
# -----------------------


def to_python_set_literal(name: str, values: Set[str]) -> str:
    """Convert set to Python literal format"""
    if not values:
        return f"{name} = set()\n"

    # Sort for consistent output
    sorted_values = sorted(values)

    # Format nicely with line breaks every 5 items
    lines = []
    current_line = []

    for i, value in enumerate(sorted_values):
        current_line.append(f'"{value}"')

        if len(current_line) == 5 or i == len(sorted_values) - 1:
            lines.append("    " + ", ".join(current_line) + ",")
            current_line = []

    body = "\n".join(lines)
    return f"{name} = {{\n{body}\n}}\n"


def write_python_output(filepath: str, short_risky: Set[str], allow_tokens: Set[str], allow_subs: Set[str]):
    """Write Python module with allowlists"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("#!/usr/bin/env python3\n")
        f.write('"""\n')
        f.write("allowlists.py\n\n")
        f.write("Auto-generated allowlists for username validation.\n")
        f.write("Generated by build_allowlists.py\n\n")
        f.write("Usage:\n")
        f.write("    from allowlists import ALLOWLIST_TOKENS, ALLOWLIST_SUBSTRINGS\n")
        f.write('"""\n\n')
        f.write("from typing import Set\n\n")

        f.write("# Short risky substrings that trigger allowlist checking\n")
        f.write(to_python_set_literal("SHORT_RISKY", short_risky))
        f.write("\n")

        f.write(f"# Legitimate words containing risky substrings ({len(allow_tokens)} words)\n")
        f.write(to_python_set_literal("ALLOWLIST_TOKENS", allow_tokens))
        f.write("\n")

        f.write(f"# Risky substrings that appear frequently in legitimate words ({len(allow_subs)} substrings)\n")
        f.write(to_python_set_literal("ALLOWLIST_SUBSTRINGS", allow_subs))


def write_json_output(filepath: str, short_risky: Set[str], allow_tokens: Set[str], allow_subs: Set[str]):
    """Write JSON file with allowlists"""
    data = {
        "SHORT_RISKY": sorted(short_risky),
        "ALLOWLIST_TOKENS": sorted(allow_tokens),
        "ALLOWLIST_SUBSTRINGS": sorted(allow_subs),
        "metadata": {
            "total_tokens": len(allow_tokens),
            "total_substrings": len(allow_subs),
            "risky_patterns": len(short_risky),
        },
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -----------------------
# MAIN
# -----------------------


def main():
    ap = argparse.ArgumentParser(description="Build allowlists for username validation")
    ap.add_argument(
        "--min-zipf",
        type=float,
        default=3.5,
        help="Minimum wordfreq zipf to include (if wordfreq available). Default 3.5",
    )
    ap.add_argument(
        "--min-length", type=int, default=3, help="Minimum token length to include in ALLOWLIST_TOKENS (default 3)"
    )
    ap.add_argument(
        "--min-hits",
        type=int,
        default=20,
        help="Minimum occurrences for a risky substring to be promoted to ALLOWLIST_SUBSTRINGS",
    )
    ap.add_argument(
        "--out-json", type=str, default="", help="Output JSON file (ALLOWLIST_TOKENS, ALLOWLIST_SUBSTRINGS)"
    )
    ap.add_argument("--out-py", type=str, default="", help="Output Python file with set literals")
    ap.add_argument("--preview", action="store_true", help="Show preview of results without writing files")
    args = ap.parse_args()

    print("Building Username Allowlists")
    print("=" * 50)
    print(f"Configuration:")
    print(f"  Short risky patterns: {len(SHORT_RISKY)}")
    print(f"  Banned words: {len(BANNED_WORDS)}")
    print(f"  Minimum word length: {args.min_length}")
    print(f"  Minimum substring hits: {args.min_hits}")
    print(f"  Wordfreq min zipf: {args.min_zipf}")
    print()

    # Load word sources
    words = load_words(min_zipf=args.min_zipf)
    print()

    # Build allowlists
    allow_tokens = build_allowlist_tokens(
        words=words,
        short_risky=SHORT_RISKY,
        banned=BANNED_WORDS,
        min_len=args.min_length,
    )
    print()

    allow_subs = build_allowlist_substrings(
        allow_tokens=allow_tokens,
        short_risky=SHORT_RISKY,
        min_hits=args.min_hits,
    )
    print()

    # Always remove anything that accidentally overlaps banned/excludes
    before_filter = len(allow_tokens)
    allow_tokens -= BANNED_WORDS | EXCLUDE_TOKENS
    allow_subs -= EXCLUDE_SUBSTRINGS

    if len(allow_tokens) < before_filter:
        print(
            f"[info] Filtered out {before_filter - len(allow_tokens)} tokens that overlapped with banned/excluded words"
        )

    # Print summary
    print("Summary:")
    print("=" * 50)
    print(f"ALLOWLIST_TOKENS: {len(allow_tokens)} words")
    print(f"ALLOWLIST_SUBSTRINGS: {len(allow_subs)} patterns")
    print()

    # Preview or write output
    if args.preview or (not args.out_json and not args.out_py):
        print("Preview of ALLOWLIST_TOKENS (first 20):")
        print("-" * 30)
        for word in sorted(list(allow_tokens))[:20]:
            print(f"  {word}")
        if len(allow_tokens) > 20:
            print(f"  ... and {len(allow_tokens) - 20} more")
        print()

        print("ALLOWLIST_SUBSTRINGS:")
        print("-" * 20)
        for sub in sorted(allow_subs):
            print(f"  {sub}")
        print()

    if args.out_json:
        write_json_output(args.out_json, SHORT_RISKY, allow_tokens, allow_subs)
        print(f"[ok] wrote JSON -> {args.out_json}")

    if args.out_py:
        write_python_output(args.out_py, SHORT_RISKY, allow_tokens, allow_subs)
        print(f"[ok] wrote Python -> {args.out_py}")

    if not args.preview and not args.out_json and not args.out_py:
        print("Use --out-py or --out-json to write output files, or --preview to see results")


if __name__ == "__main__":
    main()
