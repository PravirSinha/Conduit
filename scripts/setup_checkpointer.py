"""
CONDUIT — LangGraph Checkpoint Table Setup
Run once to create the PostgreSQL tables needed for HITL state persistence.
Usage: python scripts/setup_checkpointer.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATABASE_URL

print(f"Setting up LangGraph checkpoint tables...")
print(f"Database: {DATABASE_URL[:40]}...")

try:
    from langgraph.checkpoint.postgres import PostgresSaver

    # Version 2.0.x uses from_conn_string as a context manager
    try:
        with PostgresSaver.from_conn_string(DATABASE_URL) as saver:
            saver.setup()
            print("SUCCESS — LangGraph checkpoint tables created via context manager!")
    except TypeError:
        # Older versions return direct instance
        saver = PostgresSaver.from_conn_string(DATABASE_URL)
        saver.setup()
        print("SUCCESS — LangGraph checkpoint tables created via direct instance!")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print("Done — HITL state persistence is ready.")
