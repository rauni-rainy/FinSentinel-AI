import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pandas as pd
import pytest
from services.ingestion import clean_transaction_data
import datetime

def test_clean_transaction_data_currency():
    df = pd.DataFrame({
        "id": ["1", "2", "3"],
        "amount": ["$1,234.56", "€50.00", "1,000,000"]
    })
    cleaned = clean_transaction_data(df)
    assert cleaned.loc[cleaned["id"] == "1", "amount"].iloc[0] == 1234.56
    assert cleaned.loc[cleaned["id"] == "2", "amount"].iloc[0] == 50.00
    assert cleaned.loc[cleaned["id"] == "3", "amount"].iloc[0] == 1000000.0

def test_clean_transaction_data_duplicates():
    df = pd.DataFrame({
        "id": ["1", "1", "2"],
        "amount": [100.0, 100.0, 200.0],
        "timestamp": ["2023-01-01 10:00:00", "2023-01-01 10:00:00", "2023-01-02 10:00:00"]
    })
    cleaned = clean_transaction_data(df)
    assert len(cleaned) == 2
    assert cleaned["id"].tolist() == ["1", "2"] or cleaned["id"].tolist() == ["2", "1"]

def test_clean_transaction_data_dates():
    df = pd.DataFrame({
        "id": ["1", "2"],
        "timestamp": ["2023-01-01 15:30:00", "invalid-date"]
    })
    cleaned = clean_transaction_data(df)
    
    # Valid date should be parsed
    assert not pd.isna(cleaned.loc[cleaned['id'] == '1', 'timestamp'].iloc[0])
    # Invalid date should become NaT/Null
    assert pd.isna(cleaned.loc[cleaned['id'] == '2', 'timestamp'].iloc[0])
