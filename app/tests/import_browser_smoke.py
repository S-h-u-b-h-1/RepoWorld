"""Verify import failure readability in Chromium without using GitHub or API keys.

Run: python -m app.tests.import_browser_smoke
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]


async def verify(width: int, height: int) -> None:
    html = (ROOT / 'app/static/index.html').read_text()
    html = html.replace('<link rel="stylesheet" href="/static/styles.css">', '')
    html = html.replace('<script defer src="/static/world.js"></script>', '')
    html = html.replace('<script defer src="/static/app.js"></script>', '')
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True,
                    executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width':width,'height':height})
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        await page.set_content(html)
        await page.add_style_tag(content=(ROOT/'app/static/styles.css').read_text())
        await page.evaluate('''window.fetch=async(path,opts)=>{
          const json=path==='/api/session'?
            {authenticated:true,guest:true,csrf:'c-test',repositories:[],activeRepo:null,aiConfigured:false}:
            {error:'GitHub API rate limit reached. Please retry after cooldown.'};
          const status=path==='/api/session'?200:429;
          return new Response(JSON.stringify(json), {status,
            headers:{'Content-Type':'application/json','Retry-After':'90'}});
        }''')
        await page.add_script_tag(content=(ROOT/'app/static/world.js').read_text())
        await page.add_script_tag(content=(ROOT/'app/static/app.js').read_text())
        await page.evaluate('document.dispatchEvent(new Event("DOMContentLoaded"))')
        await page.locator('#emptyAddRepo').wait_for(state='visible',timeout=10000)
        await page.locator('#emptyAddRepo').click()
        await page.locator('#importInput').fill('public/demo')
        await page.locator('#importButton').click()
        await page.wait_for_function('!document.getElementById("importError").hidden',timeout=6000)
        message=await page.locator('#importError').inner_text()
        assert 'GitHub API rate limit reached' in message, message
        assert '2 minutes' in message, message
        assert await page.locator('#importButton').is_enabled()
        assert not await page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert not errors, errors
        print(f'{width}x{height}: import retry error readable, no JS errors or overflow')
        await browser.close()


if __name__ == '__main__':
    asyncio.run(verify(1440,900))
    asyncio.run(verify(390,844))
