#!/usr/bin/env python3
"""Quick test to see what's on demo2 page"""
import asyncio
from playwright.async_api import async_playwright
import re

async def test_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        url = "https://tds-llm-analysis.s-anand.net/demo2"
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # Get page info
        title = await page.title()
        page_url = page.url
        content = await page.content()
        text = await page.inner_text("body")
        
        print("="*80)
        print(f"Page Title: {title}")
        print(f"Page URL: {page_url}")
        print("="*80)
        print("PAGE TEXT (first 1000 chars):")
        print(text[:1000])
        print("="*80)
        print("HTML CONTENT (first 2000 chars):")
        print(content[:2000])
        print("="*80)
        
        # Extract all URLs
        urls = re.findall(r'https?://[^\s\n"\'<>]+', text)
        print(f"All URLs found in page: {urls}")
        print("="*80)
        
        # Look for forms
        forms = await page.query_selector_all("form")
        print(f"Number of forms: {len(forms)}")
        if forms:
            for i, form in enumerate(forms):
                action = await form.get_attribute("action")
                print(f"  Form {i}: action={action}")
        
        await browser.close()

asyncio.run(test_page())
