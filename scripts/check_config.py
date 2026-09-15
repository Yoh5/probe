"""Says whether the configuration is present. Never prints a value.

Run: python scripts/check_config.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
print(f".env file present        : {(ROOT / '.env').exists()}")
print(f"ASSEMBLYAI_API_KEY set   : {bool(os.environ.get('ASSEMBLYAI_API_KEY'))}")
