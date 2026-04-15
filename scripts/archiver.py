#!/usr/bin/env python3
"""
conversation-archiver — Transform chat transcripts into structured Markdown archives.

Usage:
    # Interactive mode (asks for confirmation at each step)
    python archiver.py --input conversation.txt

    # Auto mode (use suggested splits, no confirmation)
    python archiver.py --input conversation.txt --auto

    # Specify output directory
    python archiver.py --input conversation.txt --output ./archives/

    # Specify model (for Ollama or API)
    python archiver.py --input conversation.txt --model gemma4:31b

    # Dry run (show split suggestions without generating files)
    python archiver.py --input conversation.txt --dry-run

Input formats: plain text (H:/A:), JSON (messages array), Markdown (**User:**/**Assistant:**)
Output: one or more .md files following the conversation-archive protocol
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Conversation Parsing
# ---------------------------------------------------------------------------

def detect_format(text: str) -> str:
    """Detect input format: 'json', 'ha' (H:/A:), or 'markdown'."""
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(stripped)
            return "json"
        except json.JSONDecodeError:
            pass
    if re.search(r"^H:", text, re.MULTILINE):
        return "ha"
    if re.search(r"[*]{2}(?:User|Human|使用者|Assistant|AI|Claude):[*]{2}", text, re.MULTILINE | re.IGNORECASE):
        return "markdown"
    # Default: treat as H:/A: format
    return "ha"


def parse_json(text: str) -> list[dict]:
    """Parse JSON messages array into normalized turns."""
    data = json.loads(text.strip())
    if isinstance(data, dict) and "messages" in data:
        data = data["messages"]
    turns = []
    for msg in data:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        speaker = "H" if role in ("user", "human") else "A"
        turns.append({"speaker": speaker, "content": content.strip()})
    return turns


def parse_ha(text: str) -> list[dict]:
    """Parse H:/A: format into normalized turns."""
    turns = []
    current_speaker = None
    current_lines = []

    for line in text.split("\n"):
        ha_match = re.match(r"^(H|A):\s*(.*)", line)
        if ha_match:
            if current_speaker is not None:
                turns.append({
                    "speaker": current_speaker,
                    "content": "\n".join(current_lines).strip(),
                })
            current_speaker = ha_match.group(1)
            current_lines = [ha_match.group(2)]
        else:
            current_lines.append(line)

    if current_speaker is not None:
        turns.append({
            "speaker": current_speaker,
            "content": "\n".join(current_lines).strip(),
        })
    return turns


def parse_markdown(text: str) -> list[dict]:
    """Parse **User:**/**Assistant:** format into normalized turns."""
    turns = []
    current_speaker = None
    current_lines = []

    for line in text.split("\n"):
        md_match = re.match(
            r"[*]{2}(User|Human|使用者|Assistant|AI|Claude):[*]{2}\s*(.*)", line, re.IGNORECASE
        )
        if md_match:
            if current_speaker is not None:
                turns.append({
                    "speaker": current_speaker,
                    "content": "\n".join(current_lines).strip(),
                })
            role = md_match.group(1).lower()
            current_speaker = "H" if role in ("user", "human", "使用者") else "A"
            current_lines = [md_match.group(2)]
        else:
            current_lines.append(line)

    if current_speaker is not None:
        turns.append({
            "speaker": current_speaker,
            "content": "\n".join(current_lines).strip(),
        })
    return turns


def parse_conversation(text: str) -> list[dict]:
    """Auto-detect format and parse into normalized turns."""
    fmt = detect_format(text)
    if fmt == "json":
        return parse_json(text)
    elif fmt == "markdown":
        return parse_markdown(text)
    else:
        return parse_ha(text)


def turns_to_text(turns: list[dict]) -> str:
    """Convert normalized turns back to H:/A: text."""
    lines = []
    for turn in turns:
        lines.append(f"{turn['speaker']}: {turn['content']}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Split Point Detection
# ---------------------------------------------------------------------------

def build_split_prompt(conversation_text: str) -> str:
    """Build the prompt for LLM to identify split points."""
    return f"""You are a conversation analyst. Read the following conversation and identify
natural topic boundaries where the discussion shifts focus.

For each suggested split point, provide:
1. The message number (approximate) where the split occurs
2. A one-sentence description of each segment's topic

Output as JSON:
{{
  "segments": [
    {{"start_msg": 1, "end_msg": 15, "topic": "Description of segment 1"}},
    {{"start_msg": 16, "end_msg": 34, "topic": "Description of segment 2"}}
  ],
  "reasoning": "Brief explanation of why these split points were chosen"
}}

If the conversation is short and focused on one topic, return a single segment.

CONVERSATION:
{conversation_text}
"""


def build_archive_prompt(
    conversation_text: str,
    segment_topic: str,
    part_info: str,
    related_parts: list[str],
) -> str:
    """Build the prompt for LLM to generate the archive summary."""
    related_str = "\n".join(f"  - {r}" for r in related_parts) if related_parts else "  (none)"

    return f"""You are a conversation archiver. Generate a structured archive summary
following this EXACT schema. Write in the same language as the conversation.

RULES:
- 脈絡 (Context): 1-2 sentences, ~50 words
- 發展軌跡 (Development trajectory): Use A → B → C arrow format, ~300 words max
- 關鍵概念 (Key concepts): Only concepts BORN in this conversation, not referenced existing ones. Format: - **Name**: one-sentence definition
- 決議 (Decisions): Use "decided X" not "discussed X". Format: - Decided X
- 產出物 (Deliverables): Flat list, no tree structure. Format: - filename — one-sentence purpose
- 關鍵字 (Keywords): Flat tag list for RAG retrieval

OUTPUT FORMAT (output ONLY this, no preamble, no code fences):

---
type: conversation-archive
status: archived
domain: {{detect from content}}
created: {date.today().isoformat()}
archived: {date.today().isoformat()}
{part_info}tags: [detect from content]
source: detect from content
related_domains: [detect from content]
related_conversations:
{related_str}
---

# {{Generate a propositional title}}

## 脈絡

{{1-2 sentences}}

## 發展軌跡

{{A → B → C format}}

## 關鍵概念

{{Only newly born concepts}}

## 決議

{{Decisions made, not topics discussed}}

## 產出物

{{Flat list, no tree structure}}

## 關鍵字

{{Flat tag list}}

SEGMENT TOPIC: {segment_topic}

CONVERSATION:
{conversation_text}
"""


# ---------------------------------------------------------------------------
# LLM Calling
# ---------------------------------------------------------------------------

def call_llm(prompt: str, model: str) -> str:
    \"\"\"Call LLM via Ollama API (local) or OpenAI-compatible endpoint.\"\"\"
    try:
        import httpx
    except ImportError:
        print(\"Error: httpx not installed. Run: pip install httpx\", file=sys.stderr)
        sys.exit(1)

    api_base = os.environ.get(\"LLM_API_BASE\", \"http://localhost:11434\").rstrip(\"/\")
    api_key = os.environ.get(\"LLM_API_KEY\", \"\")

    # Determine if we should use Ollama format or OpenAI format
    is_ollama = \"ollama\" in api_base or api_base.endswith(\"11434\")

    try:
        if is_ollama:
            # Ollama /api/generate format
            response = httpx.post(
                f\"{api_base}/api/generate\",
                json={
                    \"model\": model,
                    \"prompt\": prompt,
                    \"stream\": False,
                    \"options\": {\"num_predict\": 4096, \"temperature\": 0.3},
                },
                timeout=300.0,
            )
            response.raise_for_status()
            return response.json().get(\"response\", \"\")
        else:
            # OpenAI-compatible /v1/chat/completions format
            headers = {\"Authorization\": f\"Bearer {api_key}\", \"Content-Type\": \"application/json\"}
            response = httpx.post(
                f\"{api_base}/v1/chat/completions\",
                headers=headers,
                json={
                    \"model\": model,
                    \"messages\": [{\"role\": \"user\", \"content\": prompt}],
                    \"temperature\": 0.3,
                },
                timeout=300.0,
            )
            response.raise_for_status()
            return response.json()[\"choices\"][0][\"message\"][\"content\"]
    except Exception as e:
        print(f\"Error calling LLM: {e}\", file=sys.stderr)
        return f\"[Error: {e}]\"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_archive(content: str) -> list[str]:
    """Validate archive format, return list of issues."""
    issues = []

    if not re.search(r"^---\s*$", content, re.MULTILINE):
        issues.append("Missing YAML frontmatter delimiters (---)")
    if "type: conversation-archive" not in content:
        issues.append("Missing 'type: conversation-archive' in frontmatter")

    required_sections = ["## 脈絡", "## 發展軌跡", "## 關鍵概念", "## 決議", "## 產出物", "## 關鍵字"]
    for section in required_sections:
        if section not in content:
            issues.append(f"Missing required section: {section}")

    return issues


# ---------------------------------------------------------------------------
# Main Workflow
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Transform conversation transcripts into structured Markdown archives"
    )
    parser.add_argument("--input", "-i", required=True, help="Path to conversation file")
    parser.add_argument("--output", "-o", default="./archives", help="Output directory")
    parser.add_argument("--model", "-m", default=None, help="LLM model name (Ollama)")
    parser.add_argument("--auto", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--dry-run", action="store_true", help="Show splits without generating")
    parser.add_argument("--slug", default=None, help="Topic slug for filenames")
    args = parser.parse_args()

    model = args.model or os.environ.get("ARCHIVER_MODEL", "gemma4:31b")

    # Read input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    raw_text = input_path.read_text(encoding="utf-8")
    turns = parse_conversation(raw_text)
    print(f"✓ Parsed {len(turns)} turns from {input_path}")

    conversation_text = turns_to_text(turns)

    # Stage 1: Scan split points
    print(f"\n📡 Scanning for split points (model: {model})...")
    split_prompt = build_split_prompt(conversation_text)
    split_response = call_llm(split_prompt, model)

    # Try to parse JSON from response
    segments = []
    try:
        # Extract JSON from response (might have surrounding text)
        json_match = re.search(r"\{.*\}", split_response, re.DOTALL)
        if json_match:
            split_data = json.loads(json_match.group())
            segments = split_data.get("segments", [])
    except (json.JSONDecodeError, AttributeError):
        pass

    if not segments:
        print("⚠ Could not parse split suggestions. Treating as single segment.")
        segments = [{"start_msg": 0, "end_msg": len(turns), "topic": "Full conversation"}]

    # Display suggestions
    print(f"\n📋 Suggested segments ({len(segments)}):")
    for i, seg in enumerate(segments, 1):
        print(f"  {i}. [{seg.get('start_msg', '?')}-{seg.get('end_msg', '?')}] {seg['topic']}")

    if args.dry_run:
        print("\n(dry run — no files generated)")
        return

    # Stage 2: Confirm
    if not args.auto and len(segments) > 1:
        confirm = input("\nAccept these splits? [Y/n/adjust] ").strip().lower()
        if confirm == "n":
            print("Treating as single segment.")
            segments = [{"start_msg": 0, "end_msg": len(turns), "topic": "Full conversation"}]
        elif confirm not in ("", "y"):
            print("(Adjustment not implemented yet — using suggested splits)")

    # Stage 3: Generate archives
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    slug = args.slug or re.sub(r"[^a-z0-9]+", "-", segments[0]["topic"].lower()[:50]).strip("-")
    is_multi = len(segments) > 1

    generated_files = []
    for i, seg in enumerate(segments):
        part_num = i + 1
        total = len(segments)

        # Slice conversation turns for this segment
        start = seg.get("start_msg", 0)
        end = seg.get("end_msg", len(turns))
        # Clamp to valid range
        start = max(0, min(start, len(turns)))
        end = max(start, min(end, len(turns)))
        segment_turns = turns[start:end] if start < end else turns

        segment_text = turns_to_text(segment_turns)

        # Build part info and related parts
        part_info = f"part: {part_num}/{total}\n" if is_multi else ""
        related_parts = []
        if is_multi:
            for j in range(total):
                if j != i:
                    other_name = f"{today}_{slug}-{j + 1}"
                    related_parts.append(other_name)

        # Generate summary
        print(f"\n📝 Generating archive {part_num}/{total}: {seg['topic']}...")
        archive_prompt = build_archive_prompt(
            segment_text, seg["topic"], part_info, related_parts
        )
        summary = call_llm(archive_prompt, model)

        # Append conversation full text
        full_archive = summary.strip() + "\n\n## 對話全文\n\n<details>\n<summary>展開原始對話"
        if is_multi:
            full_archive += f"（Part {part_num} 範圍）"
        full_archive += "</summary>\n\n" + segment_text + "\n</details>\n"

        # Validate
        issues = validate_archive(full_archive)
        if issues:
            print(f"  ⚠ Validation issues:")
            for issue in issues:
                print(f"    - {issue}")

        # Write file
        if is_multi:
            filename = f"{today}_{slug}-{part_num}.md"
        else:
            filename = f"{today}_{slug}.md"

        filepath = output_dir / filename
        filepath.write_text(full_archive, encoding="utf-8")
        generated_files.append(filepath)
        print(f"  ✓ Saved: {filepath}")

    # Summary
    print(f"\n🎯 Done! Generated {len(generated_files)} archive file(s):")
    for f in generated_files:
        size = f.stat().st_size
        print(f"  {f.name} ({size:,} bytes)")


if __name__ == "__main__":
    main()
