"""用 Playwright 抓取对话后的 DOM，确认卡片是否真的插入了。"""
import asyncio
import io

from playwright.async_api import async_playwright

OUT = io.open("D:/shot_tmp/dom_check.txt", "w", encoding="utf-8")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1249, "height": 900})
        logs = []
        page.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
        await page.goto("http://127.0.0.1:8000")
        await page.wait_for_timeout(3000)
        await page.fill("#loginEmail", "lisi2026")
        await page.fill("#loginPwd", "Test123456")
        await page.evaluate("() => auth.login()")
        await page.wait_for_timeout(4500)
        await page.click("#chatFab")
        await page.wait_for_timeout(800)
        await page.fill("#chatInput", "查一下明天贵阳到重庆的车票")
        await page.press("#chatInput", "Enter")
        await page.wait_for_timeout(32000)

        n = await page.evaluate("() => document.querySelectorAll('.toolcard').length")
        print("toolcard count:", n, file=OUT)
        print("title:", await page.title(), file=OUT)
        html = await page.evaluate(
            "() => { const b=document.querySelector('.msg.bot'); return b? b.innerHTML.slice(0,2500):'NOBOT'; }")
        print("--- bot innerHTML ---", file=OUT)
        print(html, file=OUT)
        print("--- console ---", file=OUT)
        for l in logs[-25:]:
            print(l, file=OUT)
        await browser.close()
    OUT.close()


asyncio.run(main())
