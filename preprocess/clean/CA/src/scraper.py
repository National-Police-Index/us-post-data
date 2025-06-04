# Authors: LB
# Mainrainers: LB
# Copyright:   2024, HRDAG, GPL v2 or later
# =========================================
# us-post-data/preprocess/clean/CA/scraper/scraper.py

import logging
import os
from urllib.request import urlopen

import pandas as pd
from bs4 import BeautifulSoup


# Configue the logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Create logger instance
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    with urlopen(
        "https://post.ca.gov/Peace-Officer-Certification-Actions"
    ) as url:
        soup = BeautifulSoup(url, "html.parser")
    logger.info("Connecting to site")

    html_table = soup.find_all("table")[0]

    logger.info("Connected")

    links = html_table.find_all("a")

    logger.info("Searching")

    pdf = {}
    for link in links:
        pdf[link.text] = link["href"]

    poca = pd.read_html(str(html_table))

    logger.info("Data found")
    poca_df = poca[0]

    logger.info("\n")
    logger.info(poca_df)

    new_poca_df = poca_df[poca_df["Pleadings/Orders"].notna()]
    logger.info("\n")

    logger.info(new_poca_df)
    logger.info("\n")

    logger.info("Data being exported to output directory.")
    output_path = "../output/poca_df.csv"
    dir_path = os.path.dirname(output_path)
    os.makedirs(dir_path, exist_ok=True)
    new_poca_df.to_csv(output_path, index=False)
