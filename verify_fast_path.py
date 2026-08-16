import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from backend.services.fast_path import FastPathScreener, ScreenResult

def main():
    screener = FastPathScreener()
    
    print("=== Training Normal Baseline ===")
    counts = {"PASS": 0, "AMBIGUOUS": 0, "HIGH_CONFIDENCE_FLAG": 0}
    
    # 1. Normal transactions to train the baseline
    for i in range(1, 10):
        txn = {
            "account_id": "acc_normal",
            "amount": 100.0 + (i % 5),  # amounts between 100 and 104
            "device_id": "dev_trusted",
            "merchant_id": "merch_trusted"
        }
        res = screener.fast_screen(txn)
        counts[res.name] += 1
        if i == 1:
            print(f"Txn 1 (Novel device/merchant): {res.name}")
        elif i == 2:
            print(f"Txn 2 (Known device/merchant, low velocity): {res.name}")
            
    print(f"Baseline training total splits: {counts}")
    
    print("\n=== Testing Known Anomalies ===")
    
    # 2. Anomaly: Novel Device/Merchant (AMBIGUOUS)
    txn_novel = {
        "account_id": "acc_normal",
        "amount": 101.0,
        "device_id": "dev_hacker",
        "merchant_id": "merch_shady"
    }
    res_novel = screener.fast_screen(txn_novel)
    print(f"Novel device & merchant (same baseline amount): {res_novel.name}")
    
    # 3. Anomaly: Small Spike in Z-Score (AMBIGUOUS)
    txn_small_spike = {
        "account_id": "acc_normal",
        "amount": 105.5,  # Slightly above standard deviation (Z > 2.0)
        "device_id": "dev_trusted",
        "merchant_id": "merch_trusted"
    }
    res_small_spike = screener.fast_screen(txn_small_spike)
    print(f"Small amount spike (Z-score 2-4): {res_small_spike.name}")

    # 4. Anomaly: Huge Z-Score Spike (FLAG)
    txn_huge_spike = {
        "account_id": "acc_normal",
        "amount": 5000.0, # Massive spike
        "device_id": "dev_trusted",
        "merchant_id": "merch_trusted"
    }
    res_huge_spike = screener.fast_screen(txn_huge_spike)
    print(f"Huge amount spike (Z-score > 4): {res_huge_spike.name}")

    # 5. Anomaly: Velocity Spike (FLAG)
    print("\n=== Testing Velocity Spike ===")
    for i in range(1, 55):
        txn = {
            "account_id": "acc_bot",
            "amount": 10.0,
            "device_id": "dev_bot",
            "merchant_id": "merch_bot"
        }
        res = screener.fast_screen(txn)
        if i == 1:
            print(f"Bot txn 1 (Novelty): {res.name}")
        elif i == 2:
            print(f"Bot txn 2 (Normal): {res.name}")
        elif i == 12:
            print(f"Bot txn 12 (Slight velocity spike > 10): {res.name}")
        elif i == 52:
            print(f"Bot txn 52 (Extreme velocity spike > 50): {res.name}")

if __name__ == "__main__":
    main()
