#!/usr/bin/env python3
"""Extract post content from approval file and execute twitter_poster."""

import os
import sys
from pathlib import Path

# Extract content from approval file
approval_file = Path('AI_Employee_Vault/Approved/APPROVAL_social_twitter_2026-03-06.md')
text = approval_file.read_text(encoding='utf-8')

lines = text.split('\n')
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if '## Post Content' in line:
        start_idx = i + 1
    if '## To Approve' in line:
        end_idx = i
        break

if start_idx is None or end_idx is None:
    print("[ERROR] Could not find ## Post Content or ## To Approve sections", file=sys.stderr)
    sys.exit(1)

content = '\n'.join(lines[start_idx:end_idx]).strip()
print(f"[INFO] Extracted {len(content)} chars from approval file", file=sys.stderr)
print(f"[INFO] Content:\n{content[:100]}...", file=sys.stderr)

# Import and run the poster
from twitter_poster import post_to_twitter

success = post_to_twitter(content, approval_file='APPROVAL_social_twitter_2026-03-06.md')
sys.exit(0 if success else 1)
