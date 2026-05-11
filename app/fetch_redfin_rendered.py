import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


TEXT_OUTPUT = Path("outputs/redfin_rendered_text.txt")
HTML_OUTPUT = Path("outputs/redfin_rendered.html")


def click_if_available(page, label, timeout=3000):
    candidates = [
        page.get_by_role("button", name=label),
        page.get_by_role("tab", name=label),
        page.get_by_text(label, exact=False),
    ]

    for locator in candidates:
        try:
            locator.first.click(timeout=timeout)
            page.wait_for_timeout(500)
            return True
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    return False


def save_rendered_redfin_page(url):
    Path("outputs").mkdir(exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1400})

        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=60000)

        click_if_available(page, "Property details")
        click_if_available(page, "Show all details from MLS")
        click_if_available(page, "Show all property details")

        rendered_text = page.locator("body").inner_text(timeout=30000)
        rendered_html = page.content()

        TEXT_OUTPUT.write_text(rendered_text, encoding="utf-8")
        HTML_OUTPUT.write_text(rendered_html, encoding="utf-8")

        browser.close()

    print(f"Saved rendered text to: {TEXT_OUTPUT}")
    print(f"Saved rendered HTML to: {HTML_OUTPUT}")


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 app/fetch_redfin_rendered.py "https://www.redfin.com/..."')
        return

    save_rendered_redfin_page(sys.argv[1])


if __name__ == "__main__":
    main()
