"""Daily job refresh. Exits when the batch is stored. Render cron runs this before 9:00 AM Eastern."""

from server import build_daily_batch, ensure_dirs, load_strategy


def main() -> None:
    ensure_dirs()
    batch = build_daily_batch(load_strategy(), force=True)
    jobs = batch.get("jobs") or []
    print(f"[refresh] {batch.get('date')} pool={batch.get('poolSize')} batch={len(jobs)}", flush=True)


if __name__ == "__main__":
    main()
