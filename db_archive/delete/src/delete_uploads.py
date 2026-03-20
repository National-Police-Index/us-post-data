import logging
import time

import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import (
    Aborted,
    DeadlineExceeded,
    ResourceExhausted,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# Get a Firestore client
db = firestore.client()


@retry(
    stop=stop_after_attempt(15),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type(
        (ResourceExhausted, DeadlineExceeded, Aborted)
    ),
)
def delete_batch(batch):
    try:
        batch.commit()
    except Aborted as e:
        logging.warning(f"Aborted error occurred: {str(e)}. Retrying...")
        raise


def delete_entire_uploads_collection():
    batch_size = 5000  # Reduced from 10000
    total_deleted = 0
    start_time = time.time()

    logging.info(
        f"Starting deletion of 'uploads' collection with batch size of {batch_size}"
    )

    query = db.collection("uploads").order_by("__name__")

    batch_count = 0
    while True:
        batch_start_time = time.time()

        try:
            docs = list(query.limit(batch_size).stream())

            if not docs:
                logging.info("No more documents to process. Exiting.")
                break

            batch = db.batch()
            deleted_count = 0

            for doc in docs:
                batch.delete(doc.reference)
                deleted_count += 1

            delete_batch(batch)
            total_deleted += deleted_count
            batch_count += 1

            batch_end_time = time.time()
            batch_duration = batch_end_time - batch_start_time

            logging.info(
                f"Batch {batch_count}: Deleted {deleted_count} documents in {batch_duration:.2f} seconds"
            )
            logging.info(f"Total documents deleted so far: {total_deleted}")

            last_doc = docs[-1]
            query = query.start_after(last_doc)

        except Exception as e:
            logging.error(
                f"Error occurred during batch {batch_count + 1}: {str(e)}"
            )
            logging.info("Waiting for 30 seconds before retrying...")
            time.sleep(30)

    end_time = time.time()
    total_duration = end_time - start_time

    logging.info("Finished deleting all documents in the 'uploads' collection.")
    logging.info(f"Total deleted: {total_deleted} documents")
    logging.info(f"Total batches processed: {batch_count}")
    logging.info(f"Total time taken: {total_duration:.2f} seconds")
    logging.info(
        f"Average deletion rate: {total_deleted / total_duration:.2f} documents per second"
    )


if __name__ == "__main__":
    delete_entire_uploads_collection()
