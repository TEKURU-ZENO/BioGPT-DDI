import os
import sys
from pathlib import Path

# Tests must be deterministic and offline.
os.environ["DDI_ENABLE_RXNAV"] = "false"
os.environ["BIOGPT_ENABLED"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
