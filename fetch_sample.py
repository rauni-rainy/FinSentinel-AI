import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(".env")
db_url = os.environ.get("DATABASE_URL")
engine = create_engine(db_url)

with engine.connect() as conn:
    tx_df = pd.read_sql(text("SELECT * FROM transactions LIMIT 5"), con=conn)
    audit_df = pd.read_sql(text("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 10"), con=conn)
    
    print("=== TRANSACTIONS ===")
    print(tx_df.to_markdown(index=False))
    
    print("\n=== AUDIT LOGS ===")
    if audit_df.empty:
        print("No audit logs found.")
    else:
        # truncate large JSON payloads for readability
        audit_df['payload'] = audit_df['payload'].astype(str).str.slice(0, 50) + "..."
        audit_df['result'] = audit_df['result'].astype(str).str.slice(0, 50) + "..."
        print(audit_df.to_markdown(index=False))
