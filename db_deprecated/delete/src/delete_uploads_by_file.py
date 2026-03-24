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
def delete_batch(batch):
    batch.commit()


def delete_georgia_documents_in_batches():
    batch_size = 500
    total_deleted = 0

    # Query for documents that start with "georgia-processed.csv_"
    query = (
        db.collection("db")
        .order_by("__name__")
        .start_at(["north-carolina-processed.csv_"])
        .end_at(["north-carolina-processed.csv_\uf8ff"])
    )

    while True:
        # Get the next batch of documents
        docs = list(query.limit(batch_size).stream())

        if not docs:
            break  # No more documents to process

        batch = db.batch()
        deleted_count = 0

        for doc in docs:
            batch.delete(doc.reference)
            deleted_count += 1

        # Commit the batch
        delete_batch(batch)
        total_deleted += deleted_count
        print(f"Deleted {total_deleted} documents")

        # Get the last document as a starting point for the next batch
        last_doc = docs[-1]
        query = query.start_after(last_doc)

    print(
        f"Finished deleting all Georgia documents. Total deleted: {total_deleted}"
    )


if __name__ == "__main__":
    delete_georgia_documents_in_batches()
