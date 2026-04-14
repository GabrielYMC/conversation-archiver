#!/usr/bin/env python3
"""
validate_archive.py — Check archive .md files for schema compliance.
No LLM needed — pure regex/string validation.

Usage:
    python validate_archive.py archive.md
    python validate_archive.py ./archives/*.md
    python validate_archive.py ./archives/ --recursive
"""

import argparse
import re
import sys
from pathlib import Path


def validate_file(filepath: Path) -> list[str]:
    """Validate a single archive file. Returns list of issues (empty = valid)."""
    content = filepath.read_text(encoding="utf-8")
    issues = []

    # --- Frontmatter ---
    fm_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        issues.append("❌ Missing YAML frontmatter (--- delimiters)")
        return issues  # Can't check further without frontmatter

    fm = fm_match.group(1)

    required_fm_fields = [
        ("type", r"type:\s*conversation-archive"),
        ("status", r"status:\s*(archived|checkpoint)"),
        ("domain", r"domain:\s*\S+"),
        ("created", r"created:\s*\d{4}-\d{2}-\d{2}"),
        ("archived", r"archived:\s*\d{4}-\d{2}-\d{2}"),
        ("tags", r"tags:\s*\["),
        ("source", r"source:\s*\S+"),
    ]

    for name, pattern in required_fm_fields:
        if not re.search(pattern, fm):
            issues.append(f"⚠ Frontmatter missing or malformed: {name}")

    # Check part field consistency
    part_match = re.search(r"part:\s*(\d+)/(\d+)", fm)
    if part_match:
        part_num = int(part_match.group(1))
        part_total = int(part_match.group(2))
        if part_num > part_total:
            issues.append(f"❌ Part number ({part_num}) exceeds total ({part_total})")
        # Multi-part should have related_conversations
        if "related_conversations" not in fm:
            issues.append("⚠ Multi-part archive missing related_conversations")

    # --- Required sections ---
    required_sections = {
        "脈絡": "## 脈絡",
        "發展軌跡": "## 發展軌跡",
        "關鍵概念": "## 關鍵概念",
        "決議": "## 決議",
        "產出物": "## 產出物",
        "關鍵字": "## 關鍵字",
    }

    for name, header in required_sections.items():
        if header not in content:
            issues.append(f"❌ Missing required section: {name}")

    # --- Conversation full text ---
    if "## 對話全文" not in content:
        issues.append("⚠ Missing '## 對話全文' section")
    elif "<details>" not in content:
        issues.append("⚠ 對話全文 section missing <details> wrapper")

    # --- Content quality heuristics ---
    # Check trajectory uses arrow format
    traj_match = re.search(r"## 發展軌跡\n\n(.*?)(?=\n## )", content, re.DOTALL)
    if traj_match:
        traj = traj_match.group(1)
        if "→" not in traj and "->" not in traj:
            issues.append("💡 發展軌跡 should use A → B → C arrow format")

    # Check decisions use affirmative language
    dec_match = re.search(r"## 決議\n\n(.*?)(?=\n## )", content, re.DOTALL)
    if dec_match:
        dec = dec_match.group(1)
        if "討論" in dec and "決定" not in dec:
            issues.append("💡 決議 should use '決定了 X' not '討論了 X'")

    # Check deliverables don't use tree structure
    deliv_match = re.search(r"## 產出物\n\n(.*?)(?=\n## )", content, re.DOTALL)
    if deliv_match:
        deliv = deliv_match.group(1)
        if "├" in deliv or "└" in deliv:
            issues.append("💡 產出物 should use flat list, not tree structure")

    # Word count estimate for summary (everything before 對話全文)
    summary_part = content.split("## 對話全文")[0] if "## 對話全文" in content else content
    # Remove frontmatter for count
    summary_part = re.sub(r"^---.*?---", "", summary_part, flags=re.DOTALL).strip()
    # Rough CJK + English word count
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", summary_part))
    eng_words = len(re.findall(r"[a-zA-Z]+", summary_part))
    word_count = cjk_chars + eng_words  # rough estimate
    if word_count > 1000:
        issues.append(f"💡 Summary is ~{word_count} words (soft limit: ~800). Consider session split.")
    elif word_count < 100:
        issues.append(f"💡 Summary is only ~{word_count} words. May be too sparse.")

    return issues


def main():
    parser = argparse.ArgumentParser(description="Validate conversation archive files")
    parser.add_argument("paths", nargs="+", help="Files or directories to validate")
    parser.add_argument("--recursive", "-r", action="store_true", help="Search directories recursively")
    args = parser.parse_args()

    files = []
    for p in args.paths:
        path = Path(p)
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            pattern = "**/*.md" if args.recursive else "*.md"
            files.extend(path.glob(pattern))

    if not files:
        print("No .md files found.", file=sys.stderr)
        sys.exit(1)

    total_issues = 0
    for filepath in sorted(files):
        issues = validate_file(filepath)
        status = "✅" if not issues else "⚠"
        print(f"\n{status} {filepath.name}")
        for issue in issues:
            print(f"  {issue}")
            total_issues += 1

    print(f"\n{'─' * 40}")
    print(f"Checked {len(files)} file(s), found {total_issues} issue(s)")

    sys.exit(1 if any("❌" in i for f in files for i in validate_file(f)) else 0)


if __name__ == "__main__":
    main()
