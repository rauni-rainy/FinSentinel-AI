import os
import pandas as pd
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient
import sys

# Load env
from dotenv import load_dotenv
load_dotenv(".env")

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from backend.main import app
from backend.scripts.load_paysim import load_paysim_data

def main():
    db_url = os.environ.get("DATABASE_URL")
    engine = create_engine(db_url)

    print("--- Spot-checking initial row counts ---")
    with engine.connect() as conn:
        res = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
        print(f"Current transactions count: {res}")

    if res < 10000:
        print("--- Running PaySim Loader ---")
        load_paysim_data()
        with engine.connect() as conn:
            res = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
            print(f"Transactions count after loader: {res}")
    else:
        print("PaySim loader already ran successfully.")

    print("\n--- Creating messy CSV ---")
    messy_csv_content = """id,account_id,timestamp,amount,merchant_category,merchant_id
uuid-messy-1,acc-1,2024-01-02 15:30:00,"$1,500.00",retail,merch-1
uuid-messy-1,acc-1,2024-01-02 15:30:00,"$1,500.00",retail,merch-1
uuid-messy-2,acc-2,invalid-date,€50.50,food,merch-2
"""
    with open("messy.csv", "w", encoding="utf-8") as f:
        f.write(messy_csv_content)
    
    print("Messy CSV content:")
    print(messy_csv_content)

    print("--- Uploading messy CSV through endpoint ---")
    client = TestClient(app)
    with open("messy.csv", "rb") as f:
        response = client.post("/upload-transactions", files={"file": ("messy.csv", f, "text/csv")})

    print(f"Upload response status: {response.status_code}")
    print(f"Upload response JSON: {response.json()}")

    print("\n--- Verifying clean rows landed in transactions ---")
    with engine.connect() as conn:
        new_count = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
        print(f"New transactions count: {new_count}")
        
        print("Cleaned rows inserted:")
        df = pd.read_sql(text("SELECT id, timestamp, amount FROM transactions WHERE id LIKE 'uuid-messy%'"), con=conn)
        print(df)

if __name__ == "__main__":
    main()
