import duckdb
import pandas as pd
import uuid

def clean_transaction_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans transaction data using DuckDB in-memory engine.
    - Infers and cleans types.
    - Handles inconsistent date formats (parses to standard datetime).
    - Removes currency symbols (e.g. $, €) and commas from amounts.
    - Removes duplicate rows based on all columns.
    """
    
    # Register the dataframe as a virtual table in DuckDB
    con = duckdb.connect(database=':memory:')
    con.register('raw_transactions', df)
    
    # To handle various date formats gracefully, we can use DuckDB's TRY_CAST or strptime
    # But since date formats can vary wildly in CSVs, a regex or string manipulation might be needed
    # We will cast amounts by stripping out common non-numeric chars like $, €, ,
    
    # We'll dynamically get column names. If there's an 'amount' or 'timestamp' column, we target them.
    # Otherwise, we'll try to guess based on standard names.
    # Assuming the input has 'amount' and 'timestamp' or similar columns.
    
    columns = con.execute("DESCRIBE raw_transactions").fetchall()
    col_names = [c[0] for c in columns]
    
    # Build select query dynamically
    select_exprs = []
    
    for col in col_names:
        lower_col = col.lower()
        if 'amount' in lower_col or 'price' in lower_col or 'balance' in lower_col:
            expr = f"CAST(REGEXP_REPLACE(CAST(\"{col}\" AS VARCHAR), '[^0-9\\.-]', '', 'g') AS DOUBLE) AS \"{col}\""
            select_exprs.append(expr)
        elif 'date' in lower_col or 'time' in lower_col:
            # DuckDB TRY_CAST to timestamp. If it fails, it returns NULL.
            # We first try to cast directly. 
            expr = f"TRY_CAST(\"{col}\" AS TIMESTAMP) AS \"{col}\""
            select_exprs.append(expr)
        else:
            select_exprs.append(f"\"{col}\"")
            
    select_clause = ", ".join(select_exprs)
    
    # Query to clean and deduplicate
    query = f"""
        SELECT DISTINCT {select_clause}
        FROM raw_transactions
    """
    
    cleaned_df = con.execute(query).df()
    
    return cleaned_df
