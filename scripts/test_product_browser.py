"""Product rendering fixtures only; no claim of live provider retrieval."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright,expect
async def run():
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        page=await browser.new_page(viewport={'width':390,'height':844});sent=[]
        async def reply(route):
            sent.append(route.request.post_data_json)
            await route.fulfill(json={'type':'chat','reply':'Fixture listing evidence only.','response_source':'gemini','provider_status':'ready','products':[{
              'title':'Fixture <script> product','price_inr':19999,'source_url':'https://retailer.example/item','source':'Fixture retailer','specifications':['5000 mAh (fixture)'],
              'retrieved_at':'2026-11-13T00:00:00+00:00','rating':4.2,'review_count':12}]})
        await page.route('**/api/chat',reply)
        await page.goto('http://127.0.0.1:8765')
        assert await page.locator('#allowGemini').count()==0
        await page.locator('#q').fill('Suggest a phone under ₹20,000');await page.locator('#send').click()
        await expect(page.locator('#consentModal')).to_be_visible();assert not sent
        await page.keyboard.press('Escape');assert not sent
        await page.locator('#send').click();await page.locator('#acceptProcessing').click()
        await expect(page.locator('.product-card')).to_contain_text('₹19,999')
        await expect(page.locator('.product-card')).to_contain_text('Fixture <script> product')
        assert await page.locator('.product-card script').count()==0
        assert await page.locator('.product-card a').get_attribute('href')=='https://retailer.example/item'
        await expect(page.locator('.product-card')).to_contain_text('2026-11-13T00:00:00+00:00')
        assert sent[-1]['allow_gemini'] and sent[-1]['allow_product_search']
        await page.reload();await page.locator('#q').fill('Only Samsung.');await page.locator('#send').click()
        await expect(page.locator('.product-card')).to_be_visible()
        await expect(page.locator('#consentModal')).to_be_hidden()
        await page.locator('#historyBtn').click();await page.locator('#sideSettings').click();await page.locator('#processingConsent').select_option('declined');await page.locator('#closeSettings').click()
        await page.locator('#q').fill('Battery life is my priority');await page.locator('#send').click()
        await expect(page.locator('.msg.user')).to_have_count(2)
        assert not sent[-1]['allow_gemini'] and not sent[-1]['allow_product_search']
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
        await browser.close()
    print('Passed: 8 product/consent browser checks (explicit fixtures, not live retrieval).')
if __name__=='__main__':asyncio.run(run())
