"""Print the config entry that masks an owner or owner/repo without naming it.

Usage: python scripts/mask.py my-employer-org [owner/secret-repo ...]
"""
import sys

from common import mask_key

for name in sys.argv[1:] or sys.exit(__doc__):
    print(f'{name}: "{mask_key(name)}"')
