import duckdb
import pandas as pd
import uuid

def clean_transaction_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans messy consulting/client transaction data using DuckDB in-memory engine.
    - Fuzzy matches chaotic client headers to strict PostgreSQL schema.
    - Robustly casts types, stripping currency symbols, commas, and whitespace.
    - Handles missing/NaN values by assigning default institutional placeholders.
    """
    
    # 1. Fuzzy Column Mapping
    schema_map = {
        'account_id': ['account_id', 'client account', 'acct num', 'account', 'acc_id'],
        'timestamp': ['timestamp', 'date', 'date of settlement', 'time', 'txn date', 'settlement_date'],
        'amount': ['amount', 'txn amt ($)', 'price', 'payment', 'total', 'transaction_value'],
        'merchant_category': ['merchant_category', 'category', 'industry', 'mcc', 'vendor_type'],
        'merchant_id': ['merchant_id', 'vendor', 'merchant', 'supplier', 'payee', 'client name'],
        'device_id': ['device_id', 'device', 'ip', 'terminal', 'source_ip'],
        'geo': ['geo', 'region', 'country', 'location', 'geo_location']
    }
    
    # Standardize headers in pandas first
    new_columns = {}
    for col in df.columns:
        clean_col = str(col).lower().strip()
        matched = False
        for standard_col, aliases in schema_map.items():
            if any(alias in clean_col for alias in aliases):
                new_columns[col] = standard_col
                matched = True
                break
        if not matched:
            new_columns[col] = clean_col # keep as is if no match
            
    df = df.rename(columns=new_columns)
    
    # Ensure all strict schema columns exist (Fill missing)
    strict_schema = ['account_id', 'timestamp', 'amount', 'merchant_category', 'merchant_id', 'device_id', 'geo']
    for col in strict_schema:
        if col not in df.columns:
            if col == 'amount':
                df[col] = 0.0
            elif col == 'timestamp':
                df[col] = "2026-01-01 00:00:00"
            else:
                df[col] = f"{col.upper()}_UNKNOWN"

    # Register the dataframe as a virtual table in DuckDB
    con = duckdb.connect(database=':memory:')
    con.register('raw_transactions', df)
    
    # Build select query to aggressively clean the data in-memory
    query = f"""
        SELECT DISTINCT 
            COALESCE(CAST(account_id AS VARCHAR), 'ACC_UNKNOWN') AS account_id,
            
            -- Attempt to cast timestamp, fallback to 2026-01-01
            COALESCE(TRY_CAST(timestamp AS TIMESTAMP), CAST('2026-01-01 00:00:00' AS TIMESTAMP)) AS timestamp,
            
            -- Strip out all non-numeric chars (except dot and minus) from amount
            COALESCE(
                TRY_CAST(REGEXP_REPLACE(CAST(amount AS VARCHAR), '[^0-9\\.-]', '', 'g') AS DOUBLE), 
                0.0
            ) AS amount,
            
            COALESCE(CAST(merchant_category AS VARCHAR), 'CATEGORY_UNKNOWN') AS merchant_category,
            COALESCE(CAST(merchant_id AS VARCHAR), 'VENDOR_UNKNOWN') AS merchant_id,
            COALESCE(CAST(device_id AS VARCHAR), 'DEV_UNKNOWN') AS device_id,
            COALESCE(CAST(geo AS VARCHAR), 'GEO_UNKNOWN') AS geo
        FROM raw_transactions
    """
    
    cleaned_df = con.execute(query).df()
    
    return cleaned_df
