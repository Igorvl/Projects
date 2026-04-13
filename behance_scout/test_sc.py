import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.behance.net/search/projects?search=design")
        await asyncio.sleep(3)
        cards = await page.query_selector_all("a[href*='/gallery/']")
        print(f"Found {len(cards)} cards")
        for c in cards[:5]:
            print(await c.get_attribute("href"))
        await browser.close()

asyncio.run(main())
