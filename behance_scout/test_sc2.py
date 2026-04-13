import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Loading Behance with sort...")
        await page.goto("https://www.behance.net/search/projects?search=design&sort=publishedDate")
        await asyncio.sleep(5)
        cards = await page.query_selector_all("a[href*='/gallery/']")
        print(f"Found {len(cards)} cards")
        await browser.close()

asyncio.run(main())
