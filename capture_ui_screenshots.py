#!/usr/bin/env python3
"""
Quick screenshot capture to show UI state
"""
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path
import os

async def capture_screenshots():
    """Capture screenshots of the UI"""

    print("📸 Capturing UI screenshots...")
    Path("demo_screenshots").mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})

        # Load the frontend
        html_path = Path(__file__).parent / "cerebellar_extraction_pro.html"
        await page.goto(f"file://{html_path}")
        await page.wait_for_load_state("networkidle")

        # Screenshot 1: Initial interface
        await page.screenshot(path="demo_screenshots/01_interface_initial.png", full_page=True)
        print("✅ Captured: Initial interface")

        # Try to upload PDF if it exists
        test_pdf = Path(__file__).parent / "test_cerebellar_paper.pdf"
        if test_pdf.exists():
            # Upload PDF
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(str(test_pdf))
                await asyncio.sleep(3)  # Wait for PDF to load

                # Screenshot 2: PDF loaded
                await page.screenshot(path="demo_screenshots/02_pdf_loaded.png", full_page=True)
                print("✅ Captured: PDF loaded in viewer")

                # Scroll to form
                await page.evaluate("document.querySelector('.extraction-form')?.scrollIntoView()")
                await asyncio.sleep(1)

                # Screenshot 3: Extraction form
                await page.screenshot(path="demo_screenshots/03_extraction_form.png", full_page=True)
                print("✅ Captured: Extraction form")

        await browser.close()

    print("\n✨ Screenshots saved to: demo_screenshots/")
    print("\nThese show:")
    print("  1. Initial interface with PDF viewer")
    print("  2. PDF loaded and rendered")
    print("  3. Extraction form with AI Extract buttons")

if __name__ == "__main__":
    asyncio.run(capture_screenshots())
