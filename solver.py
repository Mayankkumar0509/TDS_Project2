import asyncio
import json
import logging
import time
import re
import base64
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
import httpx
import pandas as pd
import pdfplumber

from config import (
    TEMP_DIR, TIMEOUT_SECONDS, BROWSER_TIMEOUT_MS, 
    NETWORK_IDLE_TIMEOUT_MS, MAX_FILE_SIZE_BYTES, MAX_SUBMISSION_SIZE,
    ALLOWED_SCHEMES
)
from llm_helper import llm_helper

logger = logging.getLogger(__name__)

class QuizSolver:
    """Main solver orchestrator."""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.start_time = time.time()
        self.browser: Optional[Browser] = None
        self.client = httpx.AsyncClient(timeout=30)
        self.temp_files = []
    
    async def solve(self, email: str, url: str, secret: str) -> Dict[str, Any]:
        """Main solve routine with 3-minute timeout enforcement."""
        try:
            logger.info(f"[{self.task_id}] Starting solve for {email} at {url}")
            
            result = await self._solve_loop(email, url, secret)
            
            elapsed = time.time() - self.start_time
            logger.info(f"[{self.task_id}] Completed in {elapsed:.1f}s: {result}")
            return result
        
        except Exception as e:
            logger.error(f"[{self.task_id}] Solve failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}
        
        finally:
            await self.cleanup()
    
    async def _solve_loop(self, email: str, url: str, secret: str) -> Dict[str, Any]:
        """Loop through URLs until completion or timeout."""
        current_url = url
        submission_count = 0
        
        while current_url and submission_count < 10:  # Safety limit
            if self._time_expired():
                logger.warning(f"[{self.task_id}] Timeout reached")
                return {"status": "timeout"}
            
            try:
                # Fetch and render page
                page_data = await self._fetch_and_parse_page(current_url)
                logger.info(f"[{self.task_id}] Parsed page: {page_data}")
                
                # Extract task and submission details
                task_text = page_data.get("task_text", "")
                submit_url = page_data.get("submit_url")
                submit_schema = page_data.get("submit_schema", {})
                
                if not submit_url:
                    logger.error(f"[{self.task_id}] No submit URL found")
                    return {"status": "failed", "error": "No submit URL"}
                
                # Solve the task
                answer = await self._solve_task(task_text, page_data, email, secret)
                
                # Build submission payload
                payload = self._build_payload(answer, email, secret, submit_schema)
                
                # Submit answer
                submission_count += 1
                response = await self._submit_answer(submit_url, payload)
                logger.info(f"[{self.task_id}] Submission {submission_count}: {response}")
                
                # Check if correct and follow next URL
                if response.get("correct"):
                    next_url = response.get("url")
                    if next_url:
                        current_url = next_url
                        logger.info(f"[{self.task_id}] Correct! Following next URL: {next_url}")
                    else:
                        logger.info(f"[{self.task_id}] Correct! Quiz completed.")
                        return {"status": "success", "final_response": response}
                else:
                    # Try to improve answer and resubmit
                    logger.warning(f"[{self.task_id}] Incorrect answer, will retry if time permits")
                    await asyncio.sleep(1)
            
            except Exception as e:
                logger.error(f"[{self.task_id}] Error in solve loop: {e}", exc_info=True)
                return {"status": "failed", "error": str(e)}
        
        return {"status": "completed", "submissions": submission_count}
    
    async def _fetch_and_parse_page(self, url: str) -> Dict[str, Any]:
        """Load page with Playwright and extract task/submit details."""
        if not self._is_safe_url(url):
            raise ValueError(f"Unsafe URL: {url}")
        
        if self.browser is None:
            self.browser = await self._init_browser()
        
        context = await self.browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=BROWSER_TIMEOUT_MS)
            await asyncio.sleep(1)  # Extra stability wait
            
            # Extract page content
            page_data = await self._extract_page_data(page)
            
            # Download and parse linked files
            files_data = await self._download_and_parse_files(page)
            page_data.update(files_data)
            
            return page_data
        
        finally:
            await page.close()
            await context.close()
    
    async def _extract_page_data(self, page: Page) -> Dict[str, Any]:
        """Extract task text, submit URL, and schema from DOM."""
        result = {
            "task_text": "",
            "submit_url": None,
            "submit_schema": {},
            "page_html": ""
        }
        
        try:
            # Get page HTML
            html = await page.content()
            result["page_html"] = html
            
            # Extract task text (look for main content)
            task_text = await page.evaluate("""() => {
                let text = document.body.innerText;
                return text.substring(0, 2000);
            }""")
            result["task_text"] = task_text
            
            # Try to find submit URL from script tags (look for JSON config)
            scripts = await page.query_selector_all("script")
            for script in scripts:
                try:
                    content = await script.text_content()
                    if content:
                        # Try to parse JSON from script
                        json_match = re.search(r'\{.*?"submit".*?\}', content, re.DOTALL)
                        if json_match:
                            try:
                                config = json.loads(json_match.group())
                                if "submit" in config:
                                    result["submit_url"] = config["submit"]
                                    result["submit_schema"] = config.get("schema", {})
                                    break
                            except:
                                pass
                except:
                    pass
            
            # Fallback: look for forms and links containing "submit"
            if not result["submit_url"]:
                forms = await page.query_selector_all("form")
                for form in forms:
                    action = await form.get_attribute("action")
                    if action:
                        result["submit_url"] = action
                        break
            
            # Fallback: look for data attributes or inline JSON
            if not result["submit_url"]:
                body_html = await page.inner_html("body")
                # Look for Base64 JSON
                b64_match = re.search(r'"([A-Za-z0-9+/=]{50,})"', body_html)
                if b64_match:
                    try:
                        decoded = base64.b64decode(b64_match.group(1)).decode()
                        config = json.loads(decoded)
                        if "submit" in config:
                            result["submit_url"] = config["submit"]
                    except:
                        pass
        
        except Exception as e:
            logger.warning(f"Error extracting page data: {e}")
        
        return result
    
    async def _download_and_parse_files(self, page: Page) -> Dict[str, Any]:
        """Find and download linked files (PDF, CSV, images)."""
        result = {"files_data": {}, "errors": []}
        
        try:
            links = await page.query_selector_all("a[href]")
            for link in links[:5]:  # Limit to 5 files
                try:
                    href = await link.get_attribute("href")
                    if href and any(href.endswith(ext) for ext in ['.pdf', '.csv', '.json', '.xlsx', '.png', '.jpg']):
                        file_data = await self._download_file(href)
                        if file_data:
                            result["files_data"][href] = file_data
                except:
                    pass
        
        except Exception as e:
            logger.warning(f"Error downloading files: {e}")
        
        return result
    
    async def _download_file(self, url: str) -> Optional[Dict[str, Any]]:
        """Download and parse a file."""
        try:
            # Make absolute URL if relative
            if url.startswith('/'):
                url = self._resolve_relative_url(url)
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            content = response.content
            if len(content) > MAX_FILE_SIZE_BYTES:
                logger.warning(f"File too large: {url}")
                return None
            
            filename = Path(url).name or f"file_{uuid.uuid4().hex[:8]}"
            temp_path = TEMP_DIR / filename
            temp_path.write_bytes(content)
            self.temp_files.append(temp_path)
            
            # Parse based on extension
            ext = Path(url).suffix.lower()
            data = None
            
            if ext == '.pdf':
                data = self._parse_pdf(temp_path)
            elif ext in ['.csv', '.xlsx']:
                data = self._parse_csv(temp_path)
            elif ext == '.json':
                data = json.loads(content.decode())
            elif ext in ['.png', '.jpg', '.jpeg']:
                data = self._parse_image(temp_path)
            
            return {"filename": filename, "data": data, "size": len(content)}
        
        except Exception as e:
            logger.warning(f"Error downloading file {url}: {e}")
            return None
    
    def _parse_pdf(self, path: Path) -> str:
        """Extract text from PDF."""
        try:
            with pdfplumber.open(path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
                return text[:5000]  # Limit output
        except Exception as e:
            logger.warning(f"PDF parse error: {e}")
            return ""
    
    def _parse_csv(self, path: Path) -> Any:
        """Parse CSV to list of dicts."""
        try:
            df = pd.read_csv(path)
            return df.head(20).to_dict(orient='records')
        except Exception as e:
            logger.warning(f"CSV parse error: {e}")
            return {}
    
    def _parse_image(self, path: Path) -> str:
        """Extract text from image using OCR."""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(path)
            text = pytesseract.image_to_string(img)
            return text[:1000]
        except Exception as e:
            logger.warning(f"Image OCR error: {e}")
            return ""
    
    async def _solve_task(self, task_text: str, page_data: Dict[str, Any],
                         email: str, secret: str) -> Any:
        """Analyze and solve the task using LLM."""
        try:
            # Collect context
            context = f"Files: {list(page_data.get('files_data', {}).keys())}"
            
            # Analyze task using AIML
            analysis = await llm_helper.analyze_task(task_text, context)
            logger.info(f"[{self.task_id}] Task analysis: {analysis}")
            
            # Extract data for solving
            data_str = json.dumps(page_data.get('files_data', {}), default=str)
            
            # Solve using AIML
            answer = await llm_helper.solve_task(task_text, data_str, analysis.get('task_type'))
            logger.info(f"[{self.task_id}] Answer from AIML: {answer}")
            return answer
        
        except Exception as e:
            logger.error(f"[{self.task_id}] Solve task error: {e}")
            return {"error": str(e)}
    
    def _build_payload(self, answer: Any, email: str, secret: str, 
                      schema: Dict[str, Any]) -> Dict[str, Any]:
        """Build submission payload matching expected schema."""
        payload = {
            "email": email,
            "secret": secret,
            "answer": answer
        }
        
        # Validate size
        payload_json = json.dumps(payload, default=str)
        if len(payload_json.encode()) > MAX_SUBMISSION_SIZE:
            logger.warning(f"Payload too large, truncating")
            answer_str = str(answer)[:100]
            payload["answer"] = answer_str
        
        return payload
    
    async def _submit_answer(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST answer to submit URL."""
        try:
            if not self._is_safe_url(url):
                raise ValueError(f"Unsafe submit URL: {url}")
            
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        
        except Exception as e:
            logger.error(f"[{self.task_id}] Submission error: {e}")
            return {"correct": False, "error": str(e)}
    
    def _time_expired(self) -> bool:
        """Check if 3 minutes have elapsed."""
        return (time.time() - self.start_time) > TIMEOUT_SECONDS
    
    def _is_safe_url(self, url: str) -> bool:
        """Validate URL to prevent SSRF."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.scheme in ALLOWED_SCHEMES
        except:
            return False
    
    def _resolve_relative_url(self, relative: str) -> str:
        """Resolve relative URLs (simplified)."""
        return relative  # In production, track base URL from page
    
    async def _init_browser(self) -> Browser:
        """Initialize Playwright browser."""
        playwright = await async_playwright().start()
        return await playwright.chromium.launch(headless=True)
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.browser:
                await self.browser.close()
            await self.client.aclose()
            for temp_file in self.temp_files:
                try:
                    temp_file.unlink()
                except:
                    pass
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")