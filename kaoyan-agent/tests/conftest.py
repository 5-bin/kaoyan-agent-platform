import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['AGENT_INTERNAL_KEY'] = 'test-only-internal-key-123456'
os.environ['LLM_API_KEY'] = ''
os.environ['LLM_ENABLED'] = 'false'
os.environ['RAG_BACKEND'] = 'lexical'
