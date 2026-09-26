import math
import unittest
from backoff_plan import BackoffPlan, BackoffResult


class FakeClock:
    def __init__(self, start=0.0):
        self._t = start

    def __call__(self):
        return self._t

    def advance(self, seconds):
        self._t += seconds


class CountingCallable:
    def __init__(self, succeed_at, exc=None):
        self.succeed_at = succeed_at
        self.calls = 0
        self.exc = exc if exc is not None else RuntimeError("transient")

    def __call__(self, attempt, exc):
        self.calls += 1
        if self.calls >= self.succeed_at:
            return
        raise self.exc


class TestBackoffPlan(unittest.TestCase):
    def test_succeeds_first_try_no_delays(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=1)
        plan = BackoffPlan(clock=clock)
        result = plan.run(op)
        self.assertTrue(result.success)
        self.assertEqual(result.delays, [])
        self.assertEqual(op.calls, 1)

    def test_retries_until_success(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=3)
        plan = BackoffPlan(base_delay=1.0, max_delay=10.0, clock=clock)

        def tick():
            d = plan.run(op)
            return d

        result = tick()
        self.assertTrue(result.success)
        self.assertEqual(len(result.delays), 2)
        self.assertEqual(result.delays[0], 1.0)
        self.assertEqual(result.delays[1], 2.0)

    def test_exponential_caps_at_max_delay(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=6)
        plan = BackoffPlan(base_delay=1.0, max_delay=5.0, clock=clock)
        result = plan.run(op)
        self.assertTrue(result.success)
        self.assertEqual(result.delays, [1.0, 2.0, 4.0, 5.0, 5.0])

    def test_full_jitter_bounds(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=4)
        rand_values = [0.5, 0.0, 1.0]
        idx = [0]

        def fake_rand():
            v = rand_values[idx[0]]
            idx[0] += 1
            return v

        plan = BackoffPlan(base_delay=1.0, max_delay=10.0, jitter="full", clock=clock, rand=fake_rand)
        result = plan.run(op)
        self.assertTrue(result.success)
        self.assertEqual(len(result.delays), 3)
        self.assertEqual(result.delays[0], 0.5)
        self.assertEqual(result.delays[1], 0.0)
        self.assertEqual(result.delays[2], 4.0)

    def test_deadline_truncates_last_delay(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=10)
        plan = BackoffPlan(base_delay=2.0, max_delay=10.0, deadline=3.0, clock=clock)
        result = plan.run(op)
        self.assertFalse(result.success)
        self.assertEqual(result.delays, [2.0, 1.0])
        # Second delay would be 4.0 but only 1.0 of deadline remains.
        self.assertEqual(result.delays[-1], 1.0)

    def test_deadline_zero_no_retries(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=5)
        plan = BackoffPlan(base_delay=1.0, deadline=0.0, clock=clock)
        result = plan.run(op)
        self.assertFalse(result.success)
        self.assertEqual(result.delays, [])

    def test_max_attempts_stops(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=100)
        plan = BackoffPlan(base_delay=1.0, max_delay=10.0, max_attempts=3, clock=clock)
        result = plan.run(op)
        self.assertFalse(result.success)
        self.assertEqual(len(result.delays), 2)
        self.assertEqual(op.calls, 3)

    def test_max_attempts_one(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=100)
        plan = BackoffPlan(max_attempts=1, clock=clock)
        result = plan.run(op)
        self.assertFalse(result.success)
        self.assertEqual(result.delays, [])
        self.assertEqual(op.calls, 1)

    def test_invalid_base_delay(self):
        with self.assertRaises(ValueError):
            BackoffPlan(base_delay=0)

    def test_invalid_max_delay(self):
        with self.assertRaises(ValueError):
            BackoffPlan(max_delay=-1)

    def test_invalid_deadline(self):
        with self.assertRaises(ValueError):
            BackoffPlan(deadline=-0.1)

    def test_invalid_max_attempts(self):
        with self.assertRaises(ValueError):
            BackoffPlan(max_attempts=0)

    def test_invalid_jitter(self):
        with self.assertRaises(ValueError):
            BackoffPlan(jitter="partial")

    def test_default_jitter_is_none(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=3)
        plan = BackoffPlan(base_delay=1.0, clock=clock)
        result = plan.run(op)
        self.assertEqual(result.delays, [1.0, 2.0])

    def test_default_rand_is_deterministic_half(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=3)
        plan = BackoffPlan(base_delay=2.0, jitter="full", clock=clock)
        result = plan.run(op)
        self.assertEqual(result.delays, [1.0, 2.0])

    def test_result_is_frozen_dataclass(self):
        clock = FakeClock()
        op = CountingCallable(succeed_at=1)
        plan = BackoffPlan(clock=clock)
        result = plan.run(op)
        with self.assertRaises(Exception):
            result.success = False


if __name__ == "__main__":
    unittest.main()
