"""
Delete documents from Firebase Firestore collection 'db_launch'.

Without --states: deletes ALL documents in the collection.
With --states: deletes only documents whose ID starts with
  '<state>-' (e.g. 'ca-processed.csv_0', 'ga-discipline-...').

Usage:
    python3 src/src.py                     # delete everything
    python3 src/src.py --states ca ga      # delete CA and GA only
"""

import argparse
import logging
import time

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import Aborted, DeadlineExceeded, ResourceExhausted
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

COLLECTION = "db_launch"
BATCH_SIZE = 500


@retry(
    stop=stop_after_attempt(15),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(
        (ResourceExhausted, DeadlineExceeded, Aborted)
    ),
)
def _commit(batch):
    batch.commit()


def delete_docs(db, query_fn):
    """Delete all docs returned by query_fn in batches. Returns total deleted."""
    total = 0
    batch_count = 0
    query = query_fn()

    while True:
        t0 = time.time()
        docs = list(query.limit(BATCH_SIZE).stream())
        if not docs:
            break

        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)

        _commit(batch)
        total += len(docs)
        batch_count += 1
        logging.info(
            f"Batch {batch_count}: deleted {len(docs)} docs "
            f"in {time.time() - t0:.1f}s (total: {total})"
        )
        query = query_fn().start_after(docs[-1])

    return total


def delete_all(db):
    logging.info(f"Deleting ALL documents from '{COLLECTION}'...")
    total = delete_docs(
        db,
        lambda: db.collection(COLLECTION).order_by("__name__"),
    )
    logging.info(f"Done. Total deleted: {total}")


def delete_states(db, states):
    for state in states:
        prefix = f"{state.lower()}-"
        logging.info(
            f"[{state}] Deleting documents with prefix '{prefix}'..."
        )
        total = delete_docs(
            db,
            lambda p=prefix: (
                db.collection(COLLECTION)
                .order_by("__name__")
                .start_at({u"__name__": db.collection(COLLECTION).document(p)})
                .end_before(
                    {
                        u"__name__": db.collection(COLLECTION).document(
                            p[:-1] + chr(ord(p[-2]) + 1) + "-"
                            if len(p) > 1
                            else p + "\uf8ff"
                        )
                    }
                )
            ),
        )
        logging.info(f"[{state}] Deleted {total} documents.")


def delete_states_simple(db, states):
    """Delete state docs by iterating and checking prefix (simpler, works for all cases)."""
    for state in states:
        prefix = f"{state.lower()}-"
        logging.info(
            f"[{state}] Deleting documents with prefix '{prefix}'..."
        )
        total = 0
        coll = db.collection(COLLECTION)
        last_doc = None

        while True:
            query = coll.order_by("__name__").limit(BATCH_SIZE)
            if last_doc:
                query = query.start_after(last_doc)

            docs = list(query.stream())
            if not docs:
                break

            to_delete = [d for d in docs if d.id.startswith(prefix)]
            past_prefix = any(
                not d.id.startswith(prefix) and d.id >= prefix
                for d in docs
            )

            if to_delete:
                batch = db.batch()
                for doc in to_delete:
                    batch.delete(doc.reference)
                _commit(batch)
                total += len(to_delete)
                logging.info(f"  Deleted batch of {len(to_delete)} (total: {total})")

            if past_prefix or len(docs) < BATCH_SIZE:
                break
            last_doc = docs[-1]

        logging.info(f"[{state}] Done. Total deleted: {total}")


def main():
    parser = argparse.ArgumentParser(
        description="Delete documents from Firestore db_launch collection"
    )
    parser.add_argument(
        "--states",
        nargs="+",
        metavar="STATE",
        help="Lowercase state codes to delete (default: all)",
    )
    args = parser.parse_args()

    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    t0 = time.time()
    if args.states:
        delete_states_simple(db, args.states)
    else:
        delete_all(db)
    logging.info(f"Total time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
