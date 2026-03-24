"""
Upload preprocessed state .csv.gz files to Firebase Firestore.

Reads from db/data/output/<STATE>/
Writes to Firestore collection: db_launch

Document ID pattern: <state>-processed.csv_<row_index>
                 or: <state>-discipline-processed.csv_<row_index>

Use --dry-run to validate without writing to Firebase.
"""

import argparse
import csv
import gzip
import os
import time


# Firebase imports are deferred so --dry-run works without credentials
_firebase_initialized = False


def _init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    import firebase_admin
    from firebase_admin import credentials

    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    _firebase_initialized = True


def _get_db():
    from firebase_admin import firestore

    return firestore.client()


def read_csv_gz_in_batches(file_path, batch_size=1000):
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            batch.append(row)
            if len(batch) == batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


def count_rows(file_path):
    """Count rows in a .csv.gz without loading it all into memory."""
    count = 0
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for _ in reader:
            count += 1
    return count


def doc_id_prefix(file_path):
    """Derive Firestore document ID prefix from filename.

    db/data/output/georgia/georgia-processed.csv.gz
        → "georgia-processed.csv"
    db/data/output/georgia/georgia-discipline-processed.csv.gz
        → "georgia-discipline-processed.csv"
    """
    basename = os.path.basename(file_path)  # georgia-processed.csv.gz
    return basename.replace(".gz", "")  # georgia-processed.csv


def check_state_exists(db, prefix):
    doc_ref = db.collection("db_launch").document(f"{prefix}_0")
    return doc_ref.get().exists


def delete_state_data(db, prefix):
    print(f"  Deleting existing documents for prefix '{prefix}'...")
    batch_size = 1000
    deleted = 0
    while True:
        query = (
            db.collection("db_launch")
            .order_by("__name__")
            .start_at([prefix])
            .end_at([prefix + "\uf8ff"])
            .limit(batch_size)
        )
        docs = list(query.stream())
        if not docs:
            break
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
            deleted += 1
        batch.commit()
        time.sleep(1)
    print(f"  Deleted {deleted} documents")


def upload_file(
    file_path, prefix, force=False, batch_size=1000, dry_run=False, limit=None
):
    from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    if dry_run:
        row_count = count_rows(file_path)
        effective = min(row_count, limit) if limit else row_count
        print(
            f"  [DRY RUN] Would upload {effective:,} rows as prefix '{prefix}'"
            + (f" (capped at {limit:,})" if limit and limit < row_count else "")
        )
        print(f"  [DRY RUN] First doc ID would be: {prefix}_0")
        print(f"  [DRY RUN] Last doc ID would be:  {prefix}_{effective - 1}")
        return "dry_run"

    db = _get_db()

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((ResourceExhausted, DeadlineExceeded)),
    )
    def commit_batch(b):
        b.commit()

    if force:
        if check_state_exists(db, prefix):
            delete_state_data(db, prefix)
    elif check_state_exists(db, prefix):
        print("  Skipping — data already exists (use --force to overwrite)")
        return "skipped"

    total = 0
    start_time = time.time()

    for csv_batch in read_csv_gz_in_batches(file_path, batch_size):
        fb_batch = db.batch()
        for row in csv_batch:
            if limit and total >= limit:
                break
            doc_ref = db.collection("db_launch").document(f"{prefix}_{total}")
            fb_batch.set(doc_ref, row)
            total += 1
        commit_batch(fb_batch)
        time.sleep(1)
        elapsed = time.time() - start_time
        print(f"  Committed {total:,} docs ({total / elapsed:.0f} rows/s)")
        if limit and total >= limit:
            print(f"  Reached limit of {limit:,} rows — stopping.")
            break

    elapsed = time.time() - start_time
    print(f"  Finished: {total:,} docs in {elapsed:.1f}s")
    return "success"


def find_processed_files(input_dir, states=None):
    """
    Return list of (file_path, prefix) for all .csv.gz files found under input_dir.
    Optionally filter to specific state directory names.
    """
    found = []
    if not os.path.exists(input_dir):
        return found

    state_dirs = [
        d
        for d in os.listdir(input_dir)
        if os.path.isdir(os.path.join(input_dir, d))
    ]
    if states:
        states_lower = {s.lower() for s in states}
        state_dirs = [d for d in state_dirs if d.lower() in states_lower]

    for state_dir in state_dirs:
        dir_path = os.path.join(input_dir, state_dir)
        for fname in os.listdir(dir_path):
            if fname.endswith(".csv.gz"):
                file_path = os.path.join(dir_path, fname)
                prefix = fname.replace(".gz", "")  # e.g. georgia-processed.csv
                found.append((file_path, prefix))

    return found


def main():
    parser = argparse.ArgumentParser(
        description="Upload processed state CSVs to Firebase Firestore"
    )
    parser.add_argument(
        "--input-dir",
        default="../data/output",
        help="Directory containing processed .csv.gz files (default: ../data/output)",
    )
    parser.add_argument(
        "--states",
        nargs="+",
        help="Upload only these state directories (default: all)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete and re-upload states that already exist in Firebase",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=5,
        help="Seconds to wait between file uploads (default: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate and print upload manifest without writing to Firebase. "
            "No Firebase credentials required."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Cap upload at N rows per file (for testing)",
    )
    args = parser.parse_args()

    if not args.dry_run:
        _init_firebase()

    files = find_processed_files(args.input_dir, states=args.states)
    if not files:
        print(f"No .csv.gz files found in {args.input_dir}")
        return

    if args.dry_run:
        print(f"[DRY RUN] Found {len(files)} file(s) to upload:\n")
    else:
        print(f"Found {len(files)} file(s) to upload\n")

    results = {"success": [], "skipped": [], "failed": [], "dry_run": []}

    for i, (file_path, prefix) in enumerate(files):
        state_dir = os.path.basename(os.path.dirname(file_path))
        print(f"[{state_dir}] {os.path.basename(file_path)}")

        try:
            status = upload_file(
                file_path,
                prefix,
                force=args.force,
                dry_run=args.dry_run,
                limit=args.limit,
            )
            results[status].append(prefix)
        except Exception as e:
            print(f"  Error: {e}")
            results["failed"].append(prefix)

        if not args.dry_run and i < len(files) - 1:
            print(f"  Waiting {args.delay}s...\n")
            time.sleep(args.delay)
        else:
            print()

    print("=" * 50)
    if args.dry_run:
        print(
            f"[DRY RUN] Summary: {len(results['dry_run'])} file(s) would be uploaded"
        )
        if results["failed"]:
            print(f"  Errors encountered: {len(results['failed'])}")
            for p in results["failed"]:
                print(f"    - {p}")
    else:
        print(
            f"Done. Uploaded: {len(results['success'])}  "
            f"Skipped: {len(results['skipped'])}  "
            f"Failed: {len(results['failed'])}"
        )


if __name__ == "__main__":
    main()
