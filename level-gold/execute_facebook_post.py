#!/usr/bin/env python3
"""Helper script to execute Facebook post from approval file."""

import sys
import subprocess
from pathlib import Path

def main():
    # Read the approval file
    approval_file = Path("AI_Employee_Vault/Approved/APPROVAL_social_facebook_2026-03-06.md")

    if not approval_file.exists():
        print(f"ERROR: Approval file not found: {approval_file}")
        return 1

    content = approval_file.read_text(encoding="utf-8")

    # Extract content after "## Post Content" section
    lines = content.split('\n')
    start_idx = None
    for i, line in enumerate(lines):
        if '## Post Content' in line:
            start_idx = i + 1
            break

    if start_idx is None:
        print("ERROR: Could not find '## Post Content' section")
        return 1

    # Get content until next ## section or Hashtags section
    post_lines = []
    for i in range(start_idx, len(lines)):
        if lines[i].startswith('##'):
            break
        post_lines.append(lines[i])

    post_content = '\n'.join(post_lines).strip()

    print(f"Extracted post content ({len(post_content)} chars):")
    print(post_content)
    print("\n---\nExecuting facebook_poster.py...\n")

    # Call facebook_poster
    result = subprocess.run(
        [sys.executable, "facebook_poster.py",
         "--approval-file", "APPROVAL_social_facebook_2026-03-06.md",
         "--content", post_content],
    )
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
