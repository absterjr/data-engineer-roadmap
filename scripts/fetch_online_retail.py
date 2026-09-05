"""Fetch the Online Retail dataset and convert it to CSV for the engine.

The dataset is intentionally NOT committed to the repo (data/ is
gitignored), so anyone cloning the roadmap can rebuild it with:

    python scripts/fetch_online_retail.py

Downloads the source workbook from the UCI ML Repository and converts
it to data/online_retail.csv with pandas.

HOW IT WORKS, step by step:
  1. DOWNLOAD  - urllib (stdlib) pulls a zip from UCI's static URL.
  2. UNZIP     - the zip contains the original .xlsx workbook; zipfile
                 (stdlib) extracts it into data/.
  3. CONVERT   - pandas reads the Excel sheet (needs openpyxl) and
                 writes it back out as CSV — the format the engine,
                 SQLite loader, and EDA all consume.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
DATA = Path(__file__).resolve().parent.parent / "phase-01-fundamentals" / "data"


def main() -> None:
    # make sure data/ exists before we start writing into it
    DATA.mkdir(exist_ok=True)

    print(f"Downloading {URL} ...")
    # read the whole zip into memory (it's ~25MB) rather than streaming
    # to disk - simpler, and the file is small enough
    with urllib.request.urlopen(URL) as resp:  # noqa: S310 - UCI is the dataset source
        raw = resp.read()

    # a BytesIO wraps the in-memory bytes so zipfile can treat it like a file
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        # find the workbook inside the zip whatever it happens to be named
        xlsx_name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
        z.extract(xlsx_name, DATA)

    xlsx_path = DATA / xlsx_name
    csv_path = DATA / "online_retail.csv"

    print(f"Converting {xlsx_path.name} -> {csv_path.name} ...")
    # read_excel needs openpyxl installed (pip install openpyxl)
    df = pd.read_excel(xlsx_path)
    # index=False: don't write pandas' row numbers as an extra CSV column
    df.to_csv(csv_path, index=False)

    print(f"Done: {len(df):,} rows x {df.shape[1]} cols -> {csv_path}")


if __name__ == "__main__":
    main()