import sys
import os
import uuid
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.fast_path import (
    DeviceMerchantBloomFilter,
    VelocityCountMinSketch,
    RollingZScore,
    FastPathScreener,
    ScreenResult
)

def test_bloom_filter_bounds():
    fp_target = 0.01
    n_elements = 10000
    bloom = DeviceMerchantBloomFilter(expected_elements=n_elements, fp_rate=fp_target)
    
    # Insert elements
    inserted = set()
    for _ in range(n_elements):
        item = str(uuid.uuid4())
        bloom.add(item)
        inserted.add(item)
        
    # Check false positives on completely different elements
    fp_count = 0
    n_checks = 10000
    for _ in range(n_checks):
        item = str(uuid.uuid4())
        if item not in inserted:
            if item in bloom:
                fp_count += 1
                
    actual_fp_rate = fp_count / n_checks
    print(f"\nBloom Filter Target FP Rate: {fp_target*100}%")
    print(f"Bloom Filter Actual FP Rate: {actual_fp_rate*100}% (Total FPs: {fp_count}/{n_checks})")
    
    # Assert actual is reasonably close to theoretical (allow up to 1.5% due to hash collision variance)
    assert actual_fp_rate <= (fp_target * 1.5), f"FP Rate too high! Expected <= {fp_target * 1.5}, got {actual_fp_rate}"

def test_count_min_sketch_bounds():
    epsilon = 0.001
    delta = 0.01
    cms = VelocityCountMinSketch(epsilon=epsilon, delta=delta)
    
    true_counts = {}
    total_elements = 0
    
    # Zipfian/skewed distribution
    for i in range(1, 100):
        count = int(1000 / i)
        item = f"account_{i}"
        cms.add(item, count)
        true_counts[item] = count
        total_elements += count
        
    print(f"\nCMS Total Elements Inserted: {total_elements}")
    print(f"CMS Theoretical Max Error: {epsilon * total_elements}")
    
    for item, true_count in true_counts.items():
        estimate = cms.estimate(item)
        error = estimate - true_count
        
        assert estimate >= true_count, "CMS should never underestimate"
        assert error <= (epsilon * total_elements), f"CMS error {error} exceeded theoretical bound {epsilon * total_elements}"
        
def test_rolling_z_score():
    z_tracker = RollingZScore()
    acc = "acc_1"
    
    for _ in range(5):
        z = z_tracker.check_and_update(acc, 100.0)
        assert z == 0.0
        
    z = z_tracker.check_and_update(acc, 200.0)
    assert z > 2.0  # Infinitely anomalous since stddev was 0
    
    z = z_tracker.check_and_update(acc, 300.0)
    assert z > 2.0  # Should be flagged as anomalous
    
def test_fast_screen_routing():
    screener = FastPathScreener()
    acc = "acc_routing"
    
    txn_safe = {
        "account_id": acc,
        "amount": 50.0,
        "device_id": "dev_1",
        "merchant_id": "merch_1"
    }
    
    # First transaction will be AMBIGUOUS because device/merchant are new to Bloom filter
    res = screener.fast_screen(txn_safe)
    assert res == ScreenResult.AMBIGUOUS
    
    # Second identical transaction will be PASS
    res = screener.fast_screen(txn_safe)
    assert res == ScreenResult.PASS
    
    # Spike transaction (Z-score > 4)
    txn_spike = {
        "account_id": acc,
        "amount": 10000.0,
        "device_id": "dev_1",
        "merchant_id": "merch_1"
    }
    res = screener.fast_screen(txn_spike)
    assert res == ScreenResult.HIGH_CONFIDENCE_FLAG
