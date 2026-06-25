"""Change a client's tier. Usage: python tools/set_tier.py <client_key> <1|2|3>"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import models

if len(sys.argv) != 3:
    print("Usage: python tools/set_tier.py <client_key> <tier>")
    sys.exit(1)

client_key = sys.argv[1]
tier       = int(sys.argv[2])

if tier not in (1, 2, 3):
    print("Tier must be 1, 2, or 3.")
    sys.exit(1)

client = models.get_client_by_key(client_key)
if not client:
    print(f"Client '{client_key}' not found.")
    sys.exit(1)

models.set_client_tier(client_key, tier)
print(f"'{client_key}' → Tier {tier}.")
