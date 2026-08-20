import pandas as pd
import glob
import os
import sys

sys.path.append("backend")
from services.ingestion import clean_transaction_data

files = glob.glob("demo_data/*.csv")
print(f"Testing DuckDB ingestion on {len(files)} files...")

for f in files:
    print(f"\n--- Testing {f} ---")
    raw_df = pd.read_csv(f)
    print(f"Raw Columns: {list(raw_df.columns)}")
    cleaned_df = clean_transaction_data(raw_df)
    print(f"Cleaned Columns: {list(cleaned_df.columns)}")
    print(f"Cleaned Rows: {len(cleaned_df)}")
    print(cleaned_df.head(2))
    
    # Assertions
    assert "amount" in cleaned_df.columns
    assert "account_id" in cleaned_df.columns
    assert "timestamp" in cleaned_df.columns
    assert "merchant_category" in cleaned_df.columns
    assert "merchant_id" in cleaned_df.columns
    assert "geo" in cleaned_df.columns
    assert pd.api.types.is_numeric_dtype(cleaned_df["amount"])
    print("[OK] Schema and Types Verified!")

print("\nALL FILES PASSED DUCKDB INGESTION TEST!")
