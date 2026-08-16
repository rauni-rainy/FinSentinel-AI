import math
import mmh3
from bitarray import bitarray
from enum import Enum
from typing import Dict, Any

class ScreenResult(Enum):
    PASS = "PASS"
    AMBIGUOUS = "AMBIGUOUS"
    HIGH_CONFIDENCE_FLAG = "HIGH_CONFIDENCE_FLAG"

class RollingZScore:
    def __init__(self):
        # account_id -> {"count": int, "sum": float, "sum_sq": float}
        self.stats = {}

    def check_and_update(self, account_id: str, amount: float) -> float:
        if account_id not in self.stats:
            self.stats[account_id] = {"count": 1, "sum": amount, "sum_sq": amount * amount}
            return 0.0 # Cannot compute Z-score on first transaction

        s = self.stats[account_id]
        n = s["count"]
        mean = s["sum"] / n
        variance = (s["sum_sq"] / n) - (mean * mean)
        stddev = math.sqrt(variance) if variance > 0 else 0.0

        z_score = 0.0
        if n > 1:
            if stddev > 0:
                z_score = abs(amount - mean) / stddev
            elif amount != mean:
                z_score = 999.0  # Highly anomalous if variance was exactly 0

        # Update stats
        s["count"] += 1
        s["sum"] += amount
        s["sum_sq"] += amount * amount

        return z_score

class DeviceMerchantBloomFilter:
    def __init__(self, expected_elements: int = 100000, fp_rate: float = 0.01):
        # Calculate optimal bit array size (m) and number of hash functions (k)
        self.m = int(-(expected_elements * math.log(fp_rate)) / (math.log(2) ** 2))
        self.k = int((self.m / expected_elements) * math.log(2))
        self.bit_array = bitarray(self.m)
        self.bit_array.setall(0)

    def _hashes(self, item: str) -> list[int]:
        # Generate k hash values using mmh3
        hashes = []
        for i in range(self.k):
            hashes.append(mmh3.hash(item, seed=i) % self.m)
        return hashes

    def add(self, item: str):
        for h in self._hashes(item):
            self.bit_array[h] = 1

    def __contains__(self, item: str) -> bool:
        for h in self._hashes(item):
            if not self.bit_array[h]:
                return False
        return True

class VelocityCountMinSketch:
    def __init__(self, epsilon: float = 0.001, delta: float = 0.01):
        # epsilon: error bound factor. width = e / epsilon
        # delta: probability of failing error bound. depth = ln(1 / delta)
        self.width = int(math.e / epsilon)
        self.depth = int(math.log(1 / delta))
        self.table = [[0] * self.width for _ in range(self.depth)]

    def add(self, item: str, count: int = 1):
        for i in range(self.depth):
            h = mmh3.hash(item, seed=i) % self.width
            self.table[i][h] += count

    def estimate(self, item: str) -> int:
        min_count = float('inf')
        for i in range(self.depth):
            h = mmh3.hash(item, seed=i) % self.width
            min_count = min(min_count, self.table[i][h])
        return min_count

class FastPathScreener:
    def __init__(self):
        self.z_score_tracker = RollingZScore()
        self.bloom_filter = DeviceMerchantBloomFilter()
        self.cms = VelocityCountMinSketch()

    def fast_screen(self, transaction: Dict[str, Any]) -> ScreenResult:
        account_id = transaction["account_id"]
        amount = float(transaction.get("amount", 0.0))
        device_id = transaction.get("device_id", "")
        merchant_id = transaction.get("merchant_id", "")

        # 1. Z-Score
        z = self.z_score_tracker.check_and_update(account_id, amount)

        # 2. Bloom Filter (Novelty)
        device_key = f"{account_id}:dev:{device_id}"
        merchant_key = f"{account_id}:mer:{merchant_id}"
        
        seen_device = device_key in self.bloom_filter
        seen_merchant = merchant_key in self.bloom_filter

        self.bloom_filter.add(device_key)
        self.bloom_filter.add(merchant_key)

        # 3. Velocity (Count-Min Sketch)
        velocity_key = f"{account_id}:velocity"
        self.cms.add(velocity_key, 1)
        velocity = self.cms.estimate(velocity_key)

        # Unified Decision Logic
        if z > 4.0 or velocity > 50:
            return ScreenResult.HIGH_CONFIDENCE_FLAG
        
        if (2.0 <= z <= 4.0) or not seen_device or not seen_merchant or velocity > 10:
            # Note: For the very first transaction of an account, seen_device/seen_merchant will be False,
            # triggering AMBIGUOUS. This is common in banking (new device login).
            return ScreenResult.AMBIGUOUS

        return ScreenResult.PASS
