import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


BASE_URL = "https://news.ycombinator.com"
SUBMITTED_URL = f"{BASE_URL}/submitted?id=whoishiring"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "raw"

CRAWL_DELAY_SECONDS = 30


class HNScraper:

    def __init__(self, page):
        self.page = page
        self.last_request_time = None
        self.seen_comments = set()
        self.seen_pages = set()
        self.comments = []

    async def navigate(self, url):
        if self.last_request_time is not None:
            elapsed = time.monotonic() - self.last_request_time
            wait = CRAWL_DELAY_SECONDS - elapsed

            if wait > 0:
                print(f"Waiting {wait:.1f} seconds for robots.txt...")
                await asyncio.sleep(wait)

        for attempt in range(3):
            try:
                response = await self.page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                self.last_request_time = time.monotonic()

                if response is None:
                    raise RuntimeError("No HTTP response received")

                if response.status != 200:
                    raise RuntimeError(
                        f"HTTP {response.status} for {url}"
                    )

                return

            except Exception as error:
                print(f"Request attempt {attempt + 1} failed: {error}")

                if attempt == 2:
                    raise

                await asyncio.sleep(30 * (2 ** attempt))

    async def find_current_thread(self):
        target_month = datetime.now().strftime("%B %Y")
        current_url = SUBMITTED_URL

        while current_url and current_url not in self.seen_pages:
            self.seen_pages.add(current_url)

            print("Checking submitted page:", current_url)
            await self.navigate(current_url)

            soup = BeautifulSoup(
                await self.page.content(),
                "html.parser"
            )

            for link in soup.select("tr.athing .titleline > a"):
                title = link.get_text(" ", strip=True)

                if (
                    "Ask HN: Who is hiring?" in title
                    and target_month in title
                ):
                    thread_url = urljoin(
                        BASE_URL + "/",
                        link.get("href")
                    )

                    print("Found current thread:", title)
                    print("Thread URL:", thread_url)

                    return thread_url

            more = soup.select_one("a.morelink")

            if not more:
                break

            current_url = urljoin(
                current_url,
                more.get("href")
            )

        raise RuntimeError(
            f"Could not find Who is hiring thread for {target_month}"
        )

    def extract_comments(self, html, thread_id):
        soup = BeautifulSoup(html, "html.parser")
        new_count = 0

        for row in soup.select("tr.comtr"):
            comment_id = row.get("id")

            if not comment_id or comment_id in self.seen_comments:
                continue

            comment_element = row.select_one(".commtext")

            if not comment_element:
                continue

            text = comment_element.get_text(
                " ",
                strip=True
            )

            if not text:
                continue

            author_element = row.select_one(".hnuser")
            age_element = row.select_one("span.age")
            indent_element = row.select_one("td.ind img")

            depth = 0

            if indent_element:
                try:
                    depth = int(indent_element.get("width", 0)) // 40
                except (ValueError, TypeError):
                    depth = 0

            comment = {
                "comment_id": comment_id,
                "thread_id": thread_id,
                "author": (
                    author_element.get_text(strip=True)
                    if author_element else None
                ),
                "text": text,
                "html": str(comment_element),
                "depth": depth,
                "posted_at": (
                    age_element.get("title")
                    if age_element else None
                ),
                "source_url": (
                    f"{BASE_URL}/item?id={comment_id}"
                )
            }

            self.comments.append(comment)
            self.seen_comments.add(comment_id)
            new_count += 1

        return new_count

    async def scrape_thread(self, thread_url):
        thread_id = thread_url.split("id=")[-1].split("&")[0]
        current_url = thread_url
        page_number = 0

        while current_url and current_url not in self.seen_pages:
            self.seen_pages.add(current_url)
            page_number += 1

            print(f"\nScraping thread page {page_number}")
            print(current_url)

            await self.navigate(current_url)

            html = await self.page.content()

            count = self.extract_comments(html, thread_id)

            print("New comments:", count)
            print("Total unique comments:", len(self.comments))

            soup = BeautifulSoup(html, "html.parser")
            more = soup.select_one("a.morelink")

            if not more:
                print("No more pagination links.")
                break

            current_url = urljoin(
                current_url,
                more.get("href")
            )

    def save(self, thread_url):
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        filename = RAW_DIR / (
            f"hackernews_{datetime.now().strftime('%Y-%m')}.json"
        )

        output = {
            "source": "Hacker News",
            "thread_url": thread_url,
            "scraped_at": datetime.now().isoformat(),
            "total_comments": len(self.comments),
            "comments": self.comments
        }

        with open(filename, "w", encoding="utf-8") as file:
            json.dump(
                output,
                file,
                ensure_ascii=False,
                indent=2
            )

        print("\nSCRAPING COMPLETED")
        print("Total comments:", len(self.comments))
        print("Saved file:", filename)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        page = await browser.new_page()

        scraper = HNScraper(page)

        try:
            thread_url = await scraper.find_current_thread()

            await scraper.scrape_thread(thread_url)

            scraper.save(thread_url)

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())