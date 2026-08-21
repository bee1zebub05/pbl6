import os
import re
import time
import requests
import pandas as pd

from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "http://dut.udn.vn"
PAGE_URL = BASE_URL + "/VanBanPhapQuy/page/{}"

# Ghi thẳng vào layout data/ của pipeline.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = os.path.join(ROOT, "data", "raw")
PDF_DIR = os.path.join(OUTPUT_DIR, "pdf")
METADATA_FILE = os.path.join(OUTPUT_DIR, "metadata.csv")

START_PAGE = 1
END_PAGE = 48

REQUEST_TIMEOUT = 30
RETRY = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}


# ============================================================
# SESSION
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# HELPER
# ============================================================

def clean_filename(name, max_length=180):
    """
    Làm sạch tên file để có thể lưu trên Windows/Linux.
    """

    name = str(name).strip()

    # Decode URL encoding nếu có
    name = unquote(name)

    # Thay các ký tự không hợp lệ
    name = re.sub(r'[<>:"/\\|?*]', '_', name)

    # Xóa whitespace thừa
    name = re.sub(r'\s+', ' ', name)

    # Không để dấu chấm/khoảng trắng ở cuối
    name = name.rstrip(" .")

    # Giới hạn độ dài
    return name[:max_length]


def get_html(url):
    """
    GET HTML với retry.
    """

    for attempt in range(1, RETRY + 1):

        try:
            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            # Trang này thường là Windows-1252 / UTF-8 tùy response.
            # requests có thể nhận diện encoding.
            response.encoding = response.apparent_encoding

            return response.text

        except Exception as e:

            print(
                f"[ERROR] GET {url} "
                f"(attempt {attempt}/{RETRY}): {e}"
            )

            if attempt < RETRY:
                time.sleep(2)

    return None


def download_file(url, output_path):
    """
    Download PDF với retry.
    """

    for attempt in range(1, RETRY + 1):

        try:

            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                stream=True
            )

            response.raise_for_status()

            # Kiểm tra content type
            content_type = (
                response.headers
                .get("Content-Type", "")
                .lower()
            )

            # Ghi file
            with open(output_path, "wb") as f:

                for chunk in response.iter_content(
                    chunk_size=1024 * 64
                ):

                    if chunk:
                        f.write(chunk)

            # Kiểm tra file có thực sự tồn tại
            if os.path.exists(output_path):

                size = os.path.getsize(output_path)

                if size > 1000:
                    return True

            print(
                f"[WARNING] File quá nhỏ: {output_path}"
            )

        except Exception as e:

            print(
                f"[ERROR] DOWNLOAD {url} "
                f"(attempt {attempt}/{RETRY}): {e}"
            )

            if attempt < RETRY:
                time.sleep(2)

    return False


# ============================================================
# PARSE PAGE
# ============================================================

def parse_page(html, page_number):

    soup = BeautifulSoup(html, "html.parser")

    records = []

    # Tìm bảng chứa văn bản pháp quy
    tables = soup.find_all("table")

    target_table = None

    for table in tables:

        text = table.get_text(" ", strip=True)

        if (
            "TÊN VĂN BẢN" in text
            and "SỐ HIỆU" in text
            and "TẢI VỀ" in text
        ):
            target_table = table
            break

    if target_table is None:

        print(
            f"[WARNING] Page {page_number}: "
            f"không tìm thấy bảng văn bản"
        )

        return records

    rows = target_table.find_all("tr")

    for row in rows:

        cells = row.find_all("td")

        # Header hoặc row không đúng format
        if len(cells) < 10:
            continue

        values = [
            cell.get_text(" ", strip=True)
            for cell in cells
        ]

        # ----------------------------------------------------
        # PDF LINK
        # ----------------------------------------------------

        pdf_url = None

        for a in cells[-1].find_all("a", href=True):

            href = a["href"].strip()

            if (
                ".pdf" in href.lower()
                or "download" in href.lower()
            ):
                pdf_url = urljoin(BASE_URL, href)
                break

        # Nếu không có link PDF
        if not pdf_url:
            pdf_url = None

        record = {
            "page": page_number,
            "id": values[0],
            "linh_vuc": values[1],
            "ten_van_ban": values[2],
            "so_hieu": values[3],
            "ngay_ban_hanh": values[4],
            "ngay_hieu_luc": values[5],
            "co_quan_ban_hanh": values[6],
            "loai": values[7],
            "tinh_trang": values[8],
            "pdf_url": pdf_url,
        }

        records.append(record)

    return records


# ============================================================
# CRAWL ALL PAGES
# ============================================================

all_records = []

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)


for page in range(START_PAGE, END_PAGE + 1):

    url = PAGE_URL.format(page)

    print()
    print("=" * 70)
    print(f"[PAGE {page}/{END_PAGE}]")
    print(url)
    print("=" * 70)

    html = get_html(url)

    if html is None:
        continue

    records = parse_page(
        html,
        page
    )

    print(
        f"[INFO] Found {len(records)} documents"
    )

    all_records.extend(records)

    # Nghỉ nhẹ giữa các request
    time.sleep(0.5)


# ============================================================
# DATAFRAME
# ============================================================

df = pd.DataFrame(all_records)

print()
print("=" * 70)
print("CRAWL RESULT")
print("=" * 70)

print(f"Total records: {len(df):,}")
print(
    f"Records with PDF: "
    f"{df['pdf_url'].notna().sum():,}"
)

print(
    f"Records without PDF: "
    f"{df['pdf_url'].isna().sum():,}"
)


# ============================================================
# SAVE INITIAL METADATA
# ============================================================

df.to_csv(
    METADATA_FILE,
    index=False,
    encoding="utf-8-sig"
)

print(
    f"\nMetadata saved: {METADATA_FILE}"
)


# ============================================================
# DOWNLOAD PDF
# ============================================================

success_count = 0
failed_count = 0
skip_count = 0

download_status = []


for index, row in df.iterrows():

    pdf_url = row["pdf_url"]

    if pd.isna(pdf_url) or not pdf_url:

        download_status.append("NO_PDF")
        skip_count += 1
        continue

    # --------------------------------------------------------
    # Folder theo lĩnh vực
    # --------------------------------------------------------

    category = clean_filename(
        row["linh_vuc"]
    )

    category_dir = os.path.join(
        PDF_DIR,
        category
    )

    os.makedirs(
        category_dir,
        exist_ok=True
    )

    # --------------------------------------------------------
    # File name
    # --------------------------------------------------------

    document_id = clean_filename(
        row["id"]
    )

    so_hieu = clean_filename(
        row["so_hieu"]
    )

    ten_van_ban = clean_filename(
        row["ten_van_ban"],
        max_length=120
    )

    filename = (
        f"{document_id}_{so_hieu}_{ten_van_ban}.pdf"
    )

    filepath = os.path.join(
        category_dir,
        filename
    )

    # --------------------------------------------------------
    # Nếu đã tồn tại -> skip
    # --------------------------------------------------------

    if os.path.exists(filepath):

        print(
            f"[SKIP] {index + 1}/{len(df)} "
            f"{filename}"
        )

        download_status.append("EXISTS")
        skip_count += 1

        continue

    # --------------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------------

    print()
    print(
        f"[DOWNLOAD] "
        f"{index + 1}/{len(df)}"
    )

    print(
        f"  {row['so_hieu']} - "
        f"{row['ten_van_ban']}"
    )

    print(
        f"  URL: {pdf_url}"
    )

    success = download_file(
        pdf_url,
        filepath
    )

    if success:

        print(
            f"  [OK] {filepath}"
        )

        download_status.append("DOWNLOADED")
        success_count += 1

    else:

        print(
            f"  [FAILED]"
        )

        download_status.append("FAILED")
        failed_count += 1

    # Nghỉ giữa các download
    time.sleep(0.5)


# ============================================================
# SAVE STATUS
# ============================================================

df["download_status"] = download_status

df.to_csv(
    METADATA_FILE,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 70)
print("DONE")
print("=" * 70)

print(f"Total records : {len(df):,}")
print(f"Downloaded    : {success_count:,}")
print(f"Already exist : {skip_count:,}")
print(f"Failed        : {failed_count:,}")
print(f"No PDF        : {(df['download_status'] == 'NO_PDF').sum():,}")

print()
print(f"PDF directory : {PDF_DIR}")
print(f"Metadata      : {METADATA_FILE}")