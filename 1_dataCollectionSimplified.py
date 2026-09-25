import asyncio
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

try:
    from playwright.async_api import async_playwright
except ModuleNotFoundError as error:
    raise SystemExit(
        "Playwright is required. Run: python -m pip install playwright "
        "and python -m playwright install chromium"
    ) from error


BASE_URL = "https://zagazola.org/"
MAX_LISTING_PAGES = 5
MAX_ARTICLES = 100
REQUEST_DELAY_SECONDS = 1
OUTPUT_FILE = "zagazola_crime_ranked.json"

CRIME_TERMS = {
    "terrorist": 10,
    "terrorism": 10,
    "bomb": 10,
    "explosion": 10,
    "kidnap": 10,
    "abduct": 10,
    "hostage": 9,
    "murder": 10,
    "killed": 9,
    "bandit": 9,
    "banditry": 9,
    "armed robbery": 9,
    "shooting": 8,
    "gunmen": 8,
    "rape": 8,
    "sexual assault": 8,
    "cult clash": 8,
    "arson": 7,
    "attack": 7,
    "robbery": 6,
    "cultism": 6,
    "fraud": 4,
    "theft": 4,
}

NIGERIAN_LOCATIONS = (
    "Abuja", "Lagos", "Kano", "Kaduna", "Ibadan", "Benin City", "Enugu",
    "Jos", "Maiduguri", "Port Harcourt", "Sokoto", "Katsina", "Ilorin",
    "Akure", "Owerri", "Uyo", "Calabar", "Makurdi", "Yola", "Warri",
    "Adamawa", "Bauchi", "Bayelsa", "Benue", "Borno", "Cross River",
    "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "Gombe", "Imo", "Jigawa",
    "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos",
    "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau",
    "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara", "FCT",
)


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def score_story(text):
    lowered_text = text.lower()
    score = 0
    matched_terms = []

    for term, points in CRIME_TERMS.items():
        occurrences = len(re.findall(rf"\b{re.escape(term)}\b", lowered_text))
        if occurrences:
            score += points * min(occurrences, 3)
            matched_terms.append(term)

    if re.search(r"\b(ongoing|under attack|currently happening)\b", lowered_text):
        score += 5

    if re.search(r"\b(children|school|hospital|market|passengers)\b", lowered_text):
        score += 3

    return score, matched_terms


def severity_label(score):
    if score >= 25:
        return "CRITICAL"
    if score >= 16:
        return "HIGH"
    if score >= 8:
        return "MEDIUM"
    return "LOW"


def priority_advice(score, locations):
    location_text = ", ".join(locations) if locations else "the reported area"

    if score >= 25:
        return (
            f"URGENT VERIFICATION: prioritize {location_text} for immediate "
            "incident verification and appropriate emergency response."
        )
    if score >= 16:
        return (
            f"HIGH PRIORITY: request prompt verification and increased public "
            f"safety attention around {location_text}."
        )
    if score >= 8:
        return (
            f"MEDIUM PRIORITY: verify the report and monitor {location_text} "
            "for related incidents."
        )
    return f"LOW PRIORITY: verify and monitor {location_text}."


def extract_locations(text):
    return [location for location in NIGERIAN_LOCATIONS if re.search(
        rf"\b{re.escape(location)}\b", text, flags=re.IGNORECASE
    )]


def is_zagazola_url(url):
    return urlparse(url).netloc.lower().endswith("zagazola.org")


def looks_like_article(url, link_text):
    parsed_url = urlparse(url)
    path = parsed_url.path.lower().rstrip("/")
    excluded_paths = {
        "", "/", "/about", "/contact", "/privacy-policy", "/terms",
        "/category", "/categories", "/search", "/tags", "/author",
        "/about-zagazola", "/privacy-policy", "/terms-of-service",
        "/cookie-conscent",
    }
    excluded_extensions = (".jpg", ".jpeg", ".png", ".gif", ".pdf", ".xml")

    if path in excluded_paths or path.endswith(excluded_extensions):
        return False
    if path.startswith(("/category/", "/tag/", "/author/", "/search")):
        return False

    # Zagazola may use Joomla-style, dated, or slug-based article URLs.
    return len(clean_text(link_text)) >= 20 and len(path.strip("/").split("/")) >= 1


async def listing_links(page):
    links = await page.locator("a[href]").evaluate_all(
        "elements => elements.map(element => ({href: element.href, text: element.innerText}))"
    )
    article_urls = set()

    for item in links:
        href = item["href"].split("#")[0]
        text = clean_text(item["text"])
        if (
            is_zagazola_url(href)
            and looks_like_article(href, text)
            and href.rstrip("/") != BASE_URL.rstrip("/")
        ):
            article_urls.add(href)

    return article_urls


async def next_listing_url(page):
    candidates = await page.locator(
        'a[rel="next"], a:has-text("Next"), a:has-text("Older Posts"), '
        'a:has-text("Load more")'
    ).evaluate_all(
        "elements => elements.map(element => ({href: element.href, text: element.innerText}))"
    )

    for candidate in candidates:
        href = urljoin(BASE_URL, candidate["href"])
        if not is_zagazola_url(href):
            continue
        path = urlparse(href).path.lower().rstrip("/")
        if path in {"/", "/index.php", "/index.php/about-zagazola", "/index.php/privacy-policy", "/index.php/terms-of-service", "/index.php/cookie-conscent"}:
            continue
        return href

    return None


async def extract_story(page, url):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(500)

        title_locator = page.locator("h1").first
        if await title_locator.count() == 0:
            return None
        title = clean_text(await title_locator.inner_text())

        description_locator = page.locator(
            "meta[name='description'], meta[property='og:description']"
        ).first
        summary = ""
        if await description_locator.count():
            summary = clean_text(await description_locator.get_attribute("content"))

        date_locator = page.locator(
            "time, meta[property='article:published_time'], .entry-date"
        ).first
        published_date = ""
        if await date_locator.count():
            published_date = clean_text(
                await date_locator.get_attribute("content")
                or await date_locator.inner_text()
            )

        paragraphs = await page.locator(
            "article p, .entry-content p, .post-content p"
        ).all_inner_texts()
        article_text = clean_text(" ".join(paragraphs))
        searchable_text = clean_text(f"{title} {summary} {article_text}")
        score, matched_terms = score_story(searchable_text)

        if not matched_terms:
            return None

        locations = extract_locations(searchable_text)
        return {
            "title": title,
            "url": url,
            "published_date": published_date,
            "summary": summary,
            "reported_locations": locations,
            "severity_score": score,
            "severity": severity_label(score),
            "matched_crime_terms": matched_terms,
            "police_priority": priority_advice(score, locations),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as error:
        print(f"Could not process {url}: {error}")
        return None


async def run():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
            ),
            locale="en-NG",
        )
        listing_page = await context.new_page()
        article_page = await context.new_page()
        article_urls = set()
        current_url = BASE_URL

        for page_number in range(1, MAX_LISTING_PAGES + 1):
            print(f"Scanning listing page {page_number}: {current_url}")
            try:
                await listing_page.goto(
                    current_url, wait_until="domcontentloaded", timeout=30000
                )
                await listing_page.wait_for_timeout(1000)
                article_urls.update(await listing_links(listing_page))
                if len(article_urls) >= MAX_ARTICLES:
                    break
                new_url = await next_listing_url(listing_page)
                if not new_url or new_url == current_url:
                    break
                current_url = new_url
            except Exception as error:
                print(f"Could not scan listing page: {error}")
                break

        stories = []
        for number, article_url in enumerate(list(article_urls)[:MAX_ARTICLES], 1):
            print(f"Reading article {number}/{min(len(article_urls), MAX_ARTICLES)}")
            story = await extract_story(article_page, article_url)
            if story:
                stories.append(story)
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

        stories.sort(key=lambda story: story["severity_score"], reverse=True)
        output = {
            "source": BASE_URL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": (
                "Automated news triage only. Verify every report with trusted "
                "sources before journalistic or operational use."
            ),
            "stories": stories,
        }
        with open(OUTPUT_FILE, "w", encoding="utf-8") as output_file:
            json.dump(output, output_file, ensure_ascii=False, indent=2)
        await browser.close()
        print(f"Saved {len(stories)} crime-related stories to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
