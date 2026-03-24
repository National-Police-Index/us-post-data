import argparse
import csv
import gzip
import os
import time

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import DeadlineExceeded, ResourceExhausted
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


# Initialize Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# Get a Firestore client
db = firestore.client()


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((ResourceExhausted, DeadlineExceeded)),
)
def commit_batch(batch):
    batch.commit()


def read_csv_gz_in_batches(file_path, batch_size=1000):
    with gzip.open(file_path, "rt") as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            batch.append(row)
            if len(batch) == batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


def check_state_exists(state_name):
    """Check if state data already exists in Firestore by looking for its first
    document"""
    doc_id = f"{state_name}-processed.csv_0"
    doc_ref = db.collection("db_launch").document(doc_id)
    doc = doc_ref.get()
    return doc.exists


def delete_state_data(state_name):
    """Delete all documents for a given state based on document ID pattern"""
    print(f"Deleting existing data for {state_name}...")
    batch_size = 1000
    docs_deleted = 0
    prefix = f"{state_name}-processed.csv"

    while True:
        # Get a batch of documents with matching prefix
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

        # Delete documents in batches
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
            docs_deleted += 1

        batch.commit()
        time.sleep(1)
        print(f"Deleted {docs_deleted} documents...")

    print(f"Finished deleting {docs_deleted} documents for {state_name}")


def upload_csv_gz_to_firestore(
    file_path, state_name, force=False, batch_size=1000
):
    if force:
        print(f"Force upload requested for {state_name}")
        if check_state_exists(state_name):
            print(f"Deleting existing data for {state_name}")
            delete_state_data(state_name)
        else:
            print(f"No existing data found for {state_name}")
    elif check_state_exists(state_name):
        print(f"Skipping {state_name} - data already exists in Firestore")
        return

    total_rows = 0
    start_time = time.time()

    for csv_batch in read_csv_gz_in_batches(file_path, batch_size):
        firestore_batch = db.batch()

        for row in csv_batch:
            # Removed state field as we're using document ID patterns instead
            doc_ref = db.collection("db_launch").document(
                f"{state_name}-processed.csv_{total_rows}"
            )
            firestore_batch.set(doc_ref, row)
            total_rows += 1

        commit_batch(firestore_batch)
        time.sleep(1)

        elapsed_time = time.time() - start_time
        rows_per_second = total_rows / elapsed_time
        print(
            f"Committed {total_rows} documents. Speed: {rows_per_second:.2f} rows/second"
        )

    print(f"Finished uploading {total_rows} documents from {file_path}.")
    print(f"Total time: {elapsed_time:.2f} seconds")
    print(f"Average speed: {rows_per_second:.2f} rows/second")


def main():
    parser = argparse.ArgumentParser(
        description="Upload processed CSV files to Firebase"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Input directory containing processed .csv.gz files",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=5,
        help="Delay in seconds between file uploads (default: 5)",
    )
    parser.add_argument(
        "--force-states",
        type=str,
        nargs="+",
        help="List of states to force upload (deletes existing data first)",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Force upload all states (deletes existing data first)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input_dir):
        raise ValueError(f"Input directory does not exist: {args.input_dir}")

    # Get all state directories from input
    state_dirs = [
        d
        for d in os.listdir(args.input_dir)
        if os.path.isdir(os.path.join(args.input_dir, d))
    ]

    # Convert force_states list to lowercase set for matching
    force_states = {state.lower() for state in (args.force_states or [])}

    # If force_all is True, add all available states to force_states
    if args.force_all:
        force_states = {state.lower() for state in state_dirs}
        print(f"Force uploading all {len(force_states)} available states")

    # Get all .csv.gz files from state directories
    csv_gz_files = []
    for state in state_dirs:
        state_file = os.path.join(
            args.input_dir, state, f"{state}-processed.csv.gz"
        )
        if os.path.exists(state_file):
            csv_gz_files.append(state_file)

    if not csv_gz_files:
        print(f"No .csv.gz files found in {args.input_dir}")
        return

    print(f"Found {len(csv_gz_files)} files to upload")

    skipped_states = []
    successful_states = []
    failed_states = []
    forced_states = []

    for file_path in csv_gz_files:
        state_name = os.path.basename(os.path.dirname(file_path))
        print(f"\nProcessing {state_name}...")

        try:
            force_state = state_name.lower() in force_states

            if not force_state and check_state_exists(state_name):
                print(
                    f"Skipping {state_name} - data already exists in Firebase"
                )
                skipped_states.append(state_name)
                continue

            if force_state:
                print(f"Force uploading {state_name}")
                forced_states.append(state_name)

            upload_csv_gz_to_firestore(file_path, state_name, force=force_state)
            print(f"Successfully uploaded {state_name}")
            successful_states.append(state_name)

        except Exception as e:
            print(f"Error uploading {state_name}: {str(e)}")
            failed_states.append(state_name)

        if file_path != csv_gz_files[-1]:
            print(f"Waiting {args.delay} seconds before next upload...")
            time.sleep(args.delay)

    # Print summary
    print("\nUpload Summary:")
    print(f"Successfully uploaded: {len(successful_states)} states")
    print(f"Force uploaded: {len(forced_states)} states")
    print(f"Skipped (existing data): {len(skipped_states)} states")
    print(f"Failed uploads: {len(failed_states)} states")

    if forced_states:
        print("\nForce uploaded states:")
        for state in sorted(forced_states):
            print(f"  - {state}")

    if skipped_states:
        print("\nSkipped states:")
        for state in sorted(skipped_states):
            print(f"  - {state}")

    if failed_states:
        print("\nFailed states:")
        for state in sorted(failed_states):
            print(f"  - {state}")


if __name__ == "__main__":
    main()
