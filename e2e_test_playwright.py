#!/usr/bin/env python3
"""
End-to-End Test with Playwright
Demonstrates the complete cerebellar extraction workflow with visual feedback
"""

import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright, Page
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

async def start_api_server():
    """Start Flask API server in background"""
    print("🚀 Starting Flask API server...")
    import subprocess

    # Activate venv and start server
    server_process = subprocess.Popen(
        ["python3", "api_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", "")}
    )

    # Wait for server to start
    print("⏳ Waiting for server to initialize...")
    await asyncio.sleep(3)

    # Check if server is running
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:5000/api/health", timeout=5)
        print("✅ Server started successfully!")
        return server_process
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        server_process.kill()
        return None

async def take_screenshot(page: Page, name: str, description: str):
    """Take screenshot with timestamp"""
    timestamp = time.strftime("%H%M%S")
    filename = f"screenshots/e2e_{timestamp}_{name}.png"
    Path("screenshots").mkdir(exist_ok=True)

    await page.screenshot(path=filename, full_page=True)
    print(f"📸 {description}")
    print(f"   Saved: {filename}")
    return filename

async def run_e2e_test():
    """Run complete E2E test with visual feedback"""

    print("=" * 70)
    print("🧪 CEREBELLAR EXTRACTION E2E TEST")
    print("=" * 70)
    print()

    # Check if test PDF exists
    test_pdf = "test_cerebellar_paper.pdf"
    if not os.path.exists(test_pdf):
        print(f"❌ Test PDF not found: {test_pdf}")
        return

    print(f"✅ Test PDF found: {test_pdf}")
    print()

    async with async_playwright() as p:
        # Launch browser in headed mode (visible)
        print("🌐 Launching browser...")
        browser = await p.chromium.launch(
            headless=False,  # Show browser window
            slow_mo=1000     # Slow down actions for visibility
        )

        context = await browser.new_context(
            viewport={'width': 1400, 'height': 900}
        )
        page = await context.new_page()

        try:
            # Step 1: Load the frontend
            print("\n" + "=" * 70)
            print("📄 STEP 1: Loading Frontend")
            print("=" * 70)

            frontend_path = Path(__file__).parent / "cerebellar_extraction_pro.html"
            await page.goto(f"file://{frontend_path}")

            await take_screenshot(page, "01_frontend_loaded", "Frontend loaded")
            print("✅ Frontend loaded successfully")
            await asyncio.sleep(2)

            # Step 2: Check configuration (should use real API)
            print("\n" + "=" * 70)
            print("🔧 STEP 2: Checking Configuration")
            print("=" * 70)

            # Check if using mock data
            use_mock = await page.evaluate("() => window.USE_MOCK_DATA")
            api_url = await page.evaluate("() => window.API_BASE_URL")

            print(f"   Use Mock Data: {use_mock}")
            print(f"   API URL: {api_url}")

            if use_mock:
                print("\n⚠️  WARNING: Frontend is in MOCK mode!")
                print("   To see real AI extraction, set USE_MOCK_DATA = false in HTML")

            # Step 3: Upload PDF
            print("\n" + "=" * 70)
            print("📤 STEP 3: Uploading Test PDF")
            print("=" * 70)

            # Trigger file input
            file_input = await page.query_selector('input[type="file"]')
            if file_input:
                await file_input.set_input_files(test_pdf)
                print(f"✅ Uploaded: {test_pdf}")
                await asyncio.sleep(2)
                await take_screenshot(page, "02_pdf_uploaded", "PDF uploaded to UI")
            else:
                print("❌ File input not found!")
                return

            # Wait for PDF to load in viewer
            print("⏳ Waiting for PDF to render...")
            await asyncio.sleep(3)
            await take_screenshot(page, "03_pdf_rendered", "PDF rendered in viewer")

            # Step 4: Extract a single field (Title)
            print("\n" + "=" * 70)
            print("🤖 STEP 4: Extracting Title with AI")
            print("=" * 70)

            # Find and click "AI Extract" button for title
            title_extract_btn = await page.query_selector('button[onclick*="extractField(\'title\')"]')
            if title_extract_btn:
                print("🔘 Clicking 'AI Extract' for title...")
                await title_extract_btn.click()
                await asyncio.sleep(1)

                await take_screenshot(page, "04_extracting_title", "Extracting title (loading)")

                # Wait for extraction (with timeout)
                print("⏳ Waiting for AI extraction...")
                try:
                    await page.wait_for_function(
                        "document.querySelector('#title')?.value?.length > 0",
                        timeout=30000
                    )

                    # Get extracted value
                    title_value = await page.input_value('#title')
                    print(f"✅ Title extracted: {title_value}")
                    await take_screenshot(page, "05_title_extracted", "Title extraction complete")

                except Exception as e:
                    print(f"⚠️  Extraction timeout or error: {e}")
                    await take_screenshot(page, "05_extraction_timeout", "Extraction timeout")

            # Step 5: Extract another field (DOI)
            print("\n" + "=" * 70)
            print("🤖 STEP 5: Extracting DOI")
            print("=" * 70)

            doi_extract_btn = await page.query_selector('button[onclick*="extractField(\'doi\')"]')
            if doi_extract_btn:
                print("🔘 Clicking 'AI Extract' for DOI...")
                await doi_extract_btn.click()
                await asyncio.sleep(1)

                print("⏳ Waiting for DOI extraction...")
                try:
                    await page.wait_for_function(
                        "document.querySelector('#doi')?.value?.length > 0",
                        timeout=30000
                    )

                    doi_value = await page.input_value('#doi')
                    print(f"✅ DOI extracted: {doi_value}")
                    await take_screenshot(page, "06_doi_extracted", "DOI extraction complete")

                except Exception as e:
                    print(f"⚠️  Extraction timeout or error: {e}")

            # Step 6: Try "Extract All Fields"
            print("\n" + "=" * 70)
            print("🚀 STEP 6: Extract All Fields")
            print("=" * 70)

            extract_all_btn = await page.query_selector('button[onclick*="extractAllFields"]')
            if extract_all_btn:
                print("🔘 Clicking 'Extract All Fields'...")
                await extract_all_btn.click()
                await asyncio.sleep(2)

                await take_screenshot(page, "07_extract_all_started", "Extract all started")

                print("⏳ Waiting for all extractions (this may take 30-60 seconds)...")
                print("   Multi-agent system is processing:")
                print("   - Metadata Agent (title, DOI, journal, study design)")
                print("   - Population Agent (sample sizes, criteria)")
                print("   - Intervention Agent (surgical details)")
                print("   - Outcomes Agent (mortality, mRS scores)")
                print("   - Validator Agent (consensus and validation)")

                # Wait longer for multi-agent extraction
                await asyncio.sleep(45)
                await take_screenshot(page, "08_extract_all_complete", "Extract all complete")

                # Check how many fields were filled
                filled_fields = await page.evaluate("""
                    () => {
                        const inputs = document.querySelectorAll('input[type="text"], textarea');
                        let filled = 0;
                        inputs.forEach(input => {
                            if (input.value.trim().length > 0) filled++;
                        });
                        return filled;
                    }
                """)
                print(f"✅ Filled {filled_fields} fields with extracted data")

            # Step 7: Show final results
            print("\n" + "=" * 70)
            print("📊 STEP 7: Final Results Summary")
            print("=" * 70)

            # Scroll through form to show results
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)
            await take_screenshot(page, "09_results_top", "Results - top section")

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(1)
            await take_screenshot(page, "10_results_middle", "Results - middle section")

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            await take_screenshot(page, "11_results_bottom", "Results - bottom section")

            # Get all field values
            print("\n📋 Extracted Data Summary:")
            fields = ['title', 'doi', 'pmid', 'journal', 'publication_date',
                     'study_design', 'total_sample_size', 'surgical_group_size']

            for field in fields:
                try:
                    value = await page.input_value(f'#{field}')
                    if value:
                        print(f"   {field}: {value[:60]}...")
                except:
                    pass

            # Final screenshot
            print("\n" + "=" * 70)
            print("✅ E2E TEST COMPLETED!")
            print("=" * 70)
            print()
            print("📸 All screenshots saved to: screenshots/")
            print()

            # Keep browser open for inspection
            print("🔍 Browser will remain open for 10 seconds for inspection...")
            await asyncio.sleep(10)

        except Exception as e:
            print(f"\n❌ Error during test: {e}")
            import traceback
            traceback.print_exc()
            await take_screenshot(page, "error", "Error state")

        finally:
            await browser.close()

async def main():
    """Main entry point"""

    # Check if Playwright is installed
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright not installed!")
        print("Install with: pip install playwright && playwright install chromium")
        return

    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  WARNING: ANTHROPIC_API_KEY not set!")
        print("Set it with: export ANTHROPIC_API_KEY='your-key'")
        print("Or create .env file")
        print()
        print("❌ Cannot run without API key")
        return

    # Start API server
    server_process = await start_api_server()

    if not server_process:
        print("❌ Cannot run E2E test without API server")
        return

    try:
        # Run E2E test
        await run_e2e_test()
    finally:
        # Stop server
        print("\n🛑 Stopping API server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except:
            server_process.kill()
        print("✅ Server stopped")

if __name__ == "__main__":
    asyncio.run(main())
