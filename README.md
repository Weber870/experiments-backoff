# Backoff Plan

Retry scheduling for synchronous loops with a total deadline and full jitter. Standard library only, no dependencies.

## Usage

```python
from backoff_plan import BackoffPlan

class Transient(Exception):
    pass

attempts = [0]

def operation(attempt, exc):
    attempts[0] += 1
    if attempt < 2:
        raise Transient()

plan = BackoffPlan(
    base_delay=0.5,
    max_delay=10.0,
    deadline=30.0,
    max_attempts=5,
    jitter="full",
)
result = plan.run(operation)
print(result.success, result.delays)
```

The callable you pass to `run` receives `(attempt_index, last_exception)`. Returning normally means success; raising means the operation failed and the plan decides whether to retry. The return is a `BackoffResult` with `delays` (the list of sleeps that would have occurred) and `success`.

## Why

Most retry helpers either bake in a sleep you can't see, or hand back raw delay values without enforcing a deadline. This library computes the delay schedule up front against a deadline so the caller can see exactly how many retries fit and for how long. The trade-off: `run` is synchronous and does not actually sleep — it returns the delays. If you need real sleeping, apply the delays yourself.

## Edge cases

- A `deadline` of `0` means no retries are attempted; the operation runs once and either succeeds or fails immediately.
- The last delay in a schedule may be truncated so the total scheduled time does not exceed the deadline.
- `max_attempts` includes the first attempt, so `max_attempts=1` means a single attempt with zero retries.
- `jitter="full"` multiplies each delay by a random factor in `[0, 1)`. Without `jitter`, delays are deterministic.
- The default `rand` returns `0.5` so tests and simple usage are deterministic; pass a real `random.random` for production.

## Exported names

- `BackoffPlan` — the scheduler class.
- `BackoffResult` — the frozen dataclass returned by `BackoffPlan.run`, with fields `delays: list[float]` and `success: bool`.
