import os
import pandas as pd
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))
import duckdb
from sqlalchemy import create_engine
import uuid
import random

# Make sure models are importable
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Transaction

def generate_synthetic_device_geo(row):
    """Generates synthetic device and geo data."""
    # List of common mock device/geo combinations
    geos = ["US/NY/New York", "US/CA/San Francisco", "UK/ENG/London", "FR/IDF/Paris", "IN/MH/Mumbai"]
    devices = [f"device_ios_{random.randint(100,999)}", f"device_and_{random.randint(100,999)}", "web_browser"]
    
    return pd.Series({
        "device_id": random.choice(devices),
        "geo": random.choice(geos)
    })

def load_paysim_data():
    dataset_name = "ealaxi/paysim1"
    file_name = "PS_20174392719_1491204439457_log.csv"
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    file_path = os.path.join(data_dir, file_name)
    
    if not os.path.exists(file_path):
        print(f"Downloading {dataset_name} using Kaggle API...")
        # Note: Requires ~/.kaggle/kaggle.json to be configured
        import kaggle
        kaggle.api.dataset_download_files(dataset_name, path=data_dir, unzip=True)
        print("Download complete.")
    else:
        print("Dataset already exists locally.")

    print("Loading data via DuckDB...")
    con = duckdb.connect()
    
    # PaySim columns: step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig, nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud
    # We will map this to our schema:
    # id -> uuid, account_id -> nameOrig, timestamp -> step (as hours from epoch), amount -> amount
    # merchant_category -> type, merchant_id -> nameDest
    
    # We load a sample to keep it manageable if needed, or all of it.
    # Let's load the first 10,000 rows as seed data for speed.
    query = f"""
        SELECT 
            nameOrig as account_id,
            step as step_val,
            amount,
            type as merchant_category,
            nameDest as merchant_id,
            to_json(struct_pack(oldbalanceOrg := oldbalanceOrg, newbalanceOrig := newbalanceOrig, isFraud := isFraud)) as raw_source_row
        FROM read_csv_auto('{file_path}')
        LIMIT 10000
    """
    
    df = con.execute(query).df()
    
    # Transform to schema
    print("Transforming data...")
    df['id'] = [str(uuid.uuid4()) for _ in range(len(df))]
    # step in paysim is 1 hour of time. Let's make an arbitrary start date.
    start_date = pd.Timestamp("2024-01-01 00:00:00")
    df['timestamp'] = df['step_val'].apply(lambda x: start_date + pd.Timedelta(hours=x))
    df = df.drop(columns=['step_val'])
    
    # Generate synthetic device and geo
    print("Generating synthetic device/geo data...")
    device_geo_df = df.apply(generate_synthetic_device_geo, axis=1)
    df = pd.concat([df, device_geo_df], axis=1)
    
    print(f"Prepared {len(df)} rows. Inserting into PostgreSQL...")
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    engine = create_engine(db_url)
    
    df.to_sql('transactions', engine, if_exists='append', index=False)
    print("Data ingestion complete!")

if __name__ == "__main__":
    load_paysim_data()
