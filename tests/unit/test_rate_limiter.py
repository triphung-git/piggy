"""
tests/unit/test_rate_limiter.py
-------------------------------
Kiem tra _SlidingWindowLimiter khong vuot qua 20 request/giay.
"""

import time

from backend.riot_client import _SlidingWindowLimiter


def test_sliding_window_limiter_does_not_exceed_limits():
    """Kiem tra limiter chan request thu 21 trong cua so 1 giay."""
    # Gioi han: toi da 5 requests trong 0.2 giay (tuong duong 25/giay)
    limiter = _SlidingWindowLimiter(limits=[(5, 0.2)])

    t0 = time.monotonic()
    for _ in range(5):
        limiter.acquire()
    t1 = time.monotonic()
    # 5 request dau tien phai duoc phep ngay lap tuc (< 0.05s)
    assert t1 - t0 < 0.05

    # Request thu 6 phai bi chan de cua so 0.2s troi qua
    limiter.acquire()
    t2 = time.monotonic()
    assert t2 - t0 >= 0.18, (
        f"Yeu cau thu 6 phai bi throttle it nhat ~0.2s, thuc te: {t2 - t0:.3f}s"
    )


def test_sliding_window_limiter_exact_20_per_second():
    """Kiem tra cau hinh chuan (20, 1.0): 20 request nhanh, request 21 bi sleep."""
    limiter = _SlidingWindowLimiter(limits=[(20, 0.5)])

    t0 = time.monotonic()
    for _ in range(20):
        limiter.acquire()
    t1 = time.monotonic()
    assert t1 - t0 < 0.1, "20 requests dau tien phai chay ngay lap tuc"

    limiter.acquire()
    t2 = time.monotonic()
    assert t2 - t0 >= 0.45, "Request thu 21 phai doi cua so 0.5s troi qua"
