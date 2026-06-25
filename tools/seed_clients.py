"""Populate the database with known clients. Run once after deployment."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import models

CLIENTS = [
    ("Aménagement Paysager AV",    "amenagement_paysager_rav"),
    ("Aqua Services",              "aqua_services"),
    ("Onyx Peinture",              "onyx_peinture"),
    ("Paysagement Cozzy",          "paysagement_cozzy"),
    ("Plombier Expert Terrebonne", "plombier_expert_terrebonne"),
    ("VetLife",                    "vetlife"),
]

models.init_db()
with models.get_conn() as conn:
    for name, key in CLIENTS:
        conn.execute(
            "INSERT OR IGNORE INTO clients (name, client_key, tier) VALUES (?, ?, 1)",
            (name, key),
        )

print(f"Seeded {len(CLIENTS)} clients.")
