import os
import psycopg
import uuid
import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from agents.graph import build_investigation_graph
from langgraph.checkpoint.postgres import PostgresSaver

load_dotenv()
db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")

print("Sweeping latest transactions through Anomaly Graph...")

engine = create_engine(db_url)
with engine.connect() as conn:
    # Get the 12 transactions we just uploaded (they have M- prefixes or DEV-991 etc)
    # Just grab the last 15
    result = conn.execute(text("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 15"))
    rows = [dict(row._mapping) for row in result]

print(f"Found {len(rows)} transactions to process.")

with psycopg.connect(db_url, autocommit=True) as conn:
    cp = PostgresSaver(conn)
    cp.setup()
    workflow = build_investigation_graph()
    app = workflow.compile(checkpointer=cp)
    
    for row in rows:
        print(f"Evaluating {row['id']} - ${row['amount']} @ {row['merchant_category']}")
        thread_id = f"sweep_{row['id']}_{uuid.uuid4().hex[:4]}"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Convert datetime to string for JSON serialization if needed
        if isinstance(row.get('timestamp'), datetime.datetime):
            row['timestamp'] = row['timestamp'].isoformat()
            
        # Float conversion for amounts
        if 'amount' in row and row['amount'] is not None:
            row['amount'] = float(row['amount'])
            
        initial_state = {
            "transaction": {
                "transaction_id": row["id"],
                "account_id": row.get("account_id", "ACC-UNKNOWN"),
                "amount": row.get("amount", 0.0),
                "merchant_category": row.get("merchant_category", "Unknown"),
                "merchant_id": row.get("merchant_id", "M-UNKNOWN"),
                "timestamp": row.get("timestamp", "2026-01-01T00:00:00"),
                "device_id": row.get("device_id", "DEV-UNKNOWN"),
                "geo": row.get("geo", "US-NY")
            }
        }
        
        try:
            # We don't want to block, just start the graph. It will hit interrupt() if anomalous.
            list(app.stream(initial_state, config))
        except Exception as e:
            print(f"Graph exception for {row['id']}: {e}")
            
print("Sweep complete. Check Cockpit UI for anomalies.")
