#!/usr/bin/env python3
"""
Translation updater for MF IPTV Player.

Usage:
    python update_ts.py [--lang en] [--no-compile] [--verbose]

What it does:
  1. Scans all src/*.py files for _tr("...") calls
  2. Reads existing .ts files to preserve existing translations
  3. Writes updated .ts files (new strings as unfinished, removed strings as obsolete)
  4. Compiles .ts → .qm with pyside6-lrelease

Add new languages by creating src/assets/translations/app_XX.ts manually
(copy app_en.ts, change <TS language="...">) and running this script.
"""

import argparse
import glob
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom


SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
TRANSLATIONS_DIR = os.path.join(SRC_DIR, "assets", "translations")
CONTEXT = "MainWindow"

# Regex: matches _tr("...") and _tr('...')
# Handles \n \t \uXXXX \UXXXXXXXX inside the string
_TR_PATTERN = re.compile(
    r"""_tr\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')\s*\)""",
    re.DOTALL,
)


def extract_strings(src_dir: str) -> list[str]:
    """Extract all unique _tr() strings from Python source files."""
    strings = []
    seen = set()

    for fpath in sorted(glob.glob(os.path.join(src_dir, "*.py"))):
        with open(fpath, encoding="utf-8") as f:
            content = f.read()

        for m in _TR_PATTERN.finditer(content):
            raw = m.group(1) if m.group(1) is not None else m.group(2)
            if not raw:
                continue
            # Decode Python escape sequences
            try:
                decoded = raw.encode("raw_unicode_escape").decode("unicode_escape")
            except Exception:
                decoded = raw

            if decoded and decoded not in seen:
                seen.add(decoded)
                strings.append(decoded)

    return strings


def read_ts(ts_path: str) -> dict[str, dict]:
    """
    Parse an existing .ts file.
    Returns {source_string: {"translation": str, "type": str|None}}
    type is None (finished), "unfinished", or "obsolete".
    """
    if not os.path.exists(ts_path):
        return {}

    try:
        tree = ET.parse(ts_path)
    except ET.ParseError:
        return {}

    root = tree.getroot()
    result = {}
    for ctx in root.findall("context"):
        if ctx.findtext("name") != CONTEXT:
            continue
        for msg in ctx.findall("message"):
            src = msg.findtext("source") or ""
            trans_el = msg.find("translation")
            if trans_el is None:
                continue
            translation = trans_el.text or ""
            t_type = trans_el.get("type")  # "unfinished", "obsolete", or None
            result[src] = {"translation": translation, "type": t_type}

    return result


def write_ts(ts_path: str, language: str, strings: list[str],
             existing: dict[str, dict], verbose: bool = False) -> tuple[int, int, int]:
    """
    Write updated .ts file.
    Returns (new_count, updated_count, obsolete_count).
    """
    new_count = obsolete_count = 0

    # Build message list
    messages = []
    for s in strings:
        if s in existing:
            entry = existing[s]
            # Keep existing translation as-is
            messages.append({
                "source": s,
                "translation": entry["translation"],
                "type": entry["type"],  # might be None (finished) or "unfinished"
            })
        else:
            # New string — mark unfinished, translation = source (fallback)
            messages.append({
                "source": s,
                "translation": s,
                "type": "unfinished",
            })
            new_count += 1
            if verbose:
                print(f"  [NEW]  {s!r}")

    # Detect removed strings (in existing but not in current source)
    current_sources = set(strings)
    for src, entry in existing.items():
        if src not in current_sources and entry.get("type") != "obsolete":
            # Keep as obsolete so translators know
            messages.append({
                "source": src,
                "translation": entry["translation"],
                "type": "obsolete",
            })
            obsolete_count += 1
            if verbose:
                print(f"  [OBS] {src!r}")

    # Build XML
    def esc(t: str) -> str:
        return (t.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace('"', "&quot;"))

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<!DOCTYPE TS>",
        f'<TS version="2.1" language="{language}" sourcelanguage="de">',
        f"  <context>",
        f"    <name>{CONTEXT}</name>",
    ]

    for msg in messages:
        src_esc = esc(msg["source"])
        tr_esc  = esc(msg["translation"])
        t_type  = msg["type"]

        lines.append("    <message>")
        lines.append(f"      <source>{src_esc}</source>")
        if t_type:
            lines.append(f'      <translation type="{t_type}">{tr_esc}</translation>')
        else:
            lines.append(f"      <translation>{tr_esc}</translation>")
        lines.append("    </message>")

    lines += ["  </context>", "</TS>", ""]

    with open(ts_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return new_count, 0, obsolete_count


def compile_ts(ts_path: str, qm_path: str) -> bool:
    """Compile .ts → .qm using pyside6-lrelease."""
    # Try venv first, then system
    candidates = [
        os.path.join(os.path.dirname(__file__), "venv", "bin", "pyside6-lrelease"),
        "pyside6-lrelease",
        "lrelease",
    ]
    cmd = None
    for c in candidates:
        if os.path.isfile(c) or (os.sep not in c and subprocess.run(
                ["which", c], capture_output=True).returncode == 0):
            cmd = c
            break

    if not cmd:
        print("  WARNING: pyside6-lrelease not found — skipping .qm compilation")
        return False

    result = subprocess.run(
        [cmd, ts_path, "-qm", qm_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR: lrelease failed:\n{result.stderr}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Update .ts translation files")
    parser.add_argument("--lang", default=None,
                        help="Only update this language (e.g. en). Default: all .ts files")
    parser.add_argument("--no-compile", action="store_true",
                        help="Skip .qm compilation")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print(f"Scanning {SRC_DIR}/*.py for _tr() calls...")
    strings = extract_strings(SRC_DIR)
    # Remove empty strings
    strings = [s for s in strings if s.strip()]
    print(f"  Found {len(strings)} unique translatable strings")

    # Find .ts files to update
    if args.lang:
        ts_files = [os.path.join(TRANSLATIONS_DIR, f"app_{args.lang}.ts")]
    else:
        ts_files = glob.glob(os.path.join(TRANSLATIONS_DIR, "app_*.ts"))

    if not ts_files:
        print("No .ts files found. Create one first (e.g. app_en.ts).")
        sys.exit(1)

    for ts_path in sorted(ts_files):
        lang_code = re.search(r"app_(\w+)\.ts$", ts_path)
        lang = lang_code.group(1) if lang_code else "??"
        lang_tag = {"en": "en_US", "de": "de_DE", "fr": "fr_FR", "tr": "tr_TR"}.get(lang, lang)

        print(f"\nUpdating {os.path.basename(ts_path)} [{lang_tag}]...")
        existing = read_ts(ts_path)
        print(f"  Existing: {len(existing)} strings")

        new_c, upd_c, obs_c = write_ts(ts_path, lang_tag, strings, existing, args.verbose)
        total = len(strings)
        finished = sum(1 for e in existing.values() if e.get("type") is None)
        print(f"  Result:  {total} strings | {new_c} new | {obs_c} obsolete | "
              f"{finished} finished translations")

        if not args.no_compile:
            qm_path = ts_path.replace(".ts", ".qm")
            ok = compile_ts(ts_path, qm_path)
            if ok:
                size = os.path.getsize(qm_path)
                print(f"  Compiled: {os.path.basename(qm_path)} ({size:,} bytes)")

    print("\nDone.")


if __name__ == "__main__":
    main()
