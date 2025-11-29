# === solver.py (UPDATED) ===
import os
import re
import json
import asyncio
import logging
import tempfile
import shutil
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Union
from urllib.parse import urljoin

import httpx
import pandas as pd
from playwright.async_api import async_playwright

from llm_helper import LLMHelper

logger = logging.getLogger(__name__)

class QuizSolver:
    def __init__(self, request_id: str, email: str, secret: str, start_time: datetime, timeout_seconds: int):
        self.request_id = request_id
        self.email = email
        self.secret = secret
        self.start_time = start_time
        self.timeout_seconds = timeout_seconds
        self.temp_dir = tempfile.mkdtemp(prefix=f"quiz_{request_id}_")
        self.llm_helper = LLMHelper()
        self.max_file_size = 5 * 1024 * 1024  # 5MB
        self.max_payload_size = 1 * 1024 * 1024  # 1MB
        self.submission_attempts = {}  # Track attempts per URL
        
    def __del__(self):
        """Cleanup temp directory."""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
    def _time_remaining(self) -> float:
        """Get remaining time in seconds."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return max(0, self.timeout_seconds - elapsed)
    
    def _is_timeout(self) -> bool:
        """Check if timeout exceeded."""
        return self._time_remaining() <= 0
    
    async def solve(self, initial_url: str) -> Dict[str, Any]:
        """Main solver routine - solve quizzes following next URLs."""
        current_url = initial_url
        attempts = 0
        max_attempts = 10
        status = "completed"
        failure_reason = None
        
        while current_url and attempts < max_attempts and not self._is_timeout():
            attempts += 1
            logger.info(f"[{self.request_id}] Attempt {attempts}: Solving {current_url}")
            
            if self._is_timeout():
                logger.warning(f"[{self.request_id}] Timeout reached after {attempts-1} attempts")
                status = "timeout"
                break
            
            try:
                task_data = await self._extract_task(current_url)
                if not task_data:
                    logger.error(f"[{self.request_id}] Failed to extract task from {current_url}")
                    status = "failed"
                    failure_reason = "Failed to extract task"
                    break
                
                # Check if submit URL is available
                if not task_data.get("submit_url"):
                    # If no submit URL found, this might be a results page
                    page_text = task_data.get("task_text", "")
                    if "congratulations" in page_text.lower() or "completed" in page_text.lower() or "success" in page_text.lower():
                        logger.info(f"[{self.request_id}] Quiz appears to be completed (results page)")
                        status = "success"
                        break
                    else:
                        logger.error(f"[{self.request_id}] No submit URL found - cannot proceed")
                        logger.debug(f"[{self.request_id}] Page content: {page_text[:500]}")
                        status = "failed"
                        failure_reason = "No submit URL found in page"
                        break
                
                answer = await self._compute_answer(task_data)
                if not answer:
                    logger.error(f"[{self.request_id}] Failed to compute answer")
                    status = "failed"
                    failure_reason = "Failed to compute answer"
                    break
                
                logger.info(f"[{self.request_id}] Computed answer: {answer}")
                
                # Convert answer to proper format
                formatted_answer = self._format_answer(answer)
                
                result = await self._submit_answer(task_data, formatted_answer)
                if not result:
                    logger.warning(f"[{self.request_id}] Submission failed")
                    status = "failed"
                    failure_reason = "Submission request failed"
                    break
                
                logger.info(f"[{self.request_id}] Submit response: {result}")
                
                # Check if correct
                if result.get("correct"):
                    logger.info(f"[{self.request_id}] Answer correct!")
                    if result.get("url"):
                        current_url = result["url"]
                        logger.info(f"[{self.request_id}] Following next URL: {current_url}")
                    else:
                        logger.info(f"[{self.request_id}] Quiz completed!")
                        status = "success"
                        break
                else:
                    # Wrong answer - try to improve and re-submit
                    logger.warning(f"[{self.request_id}] Answer incorrect: {result.get('reason')}")
                    
                    # Try to re-submit with different answer if time permits
                    if self._time_remaining() > 30:
                        improved_answer = await self._compute_answer(task_data, retry=True)
                        if improved_answer and improved_answer != answer:
                            logger.info(f"[{self.request_id}] Re-submitting with improved answer: {improved_answer}")
                            formatted_answer = self._format_answer(improved_answer)
                            result = await self._submit_answer(task_data, formatted_answer)
                            if result and result.get("correct"):
                                if result.get("url"):
                                    current_url = result["url"]
                                    logger.info(f"[{self.request_id}] Following next URL: {current_url}")
                                else:
                                    status = "success"
                                    break
                            elif result and result.get("url"):
                                # Move to next URL even if wrong
                                current_url = result["url"]
                                logger.info(f"[{self.request_id}] Following provided next URL: {current_url}")
                            else:
                                status = "failed"
                                failure_reason = "Wrong answer and no next URL provided"
                                break
                        else:
                            # Check if new URL provided
                            if result.get("url"):
                                current_url = result["url"]
                                logger.info(f"[{self.request_id}] Following provided next URL: {current_url}")
                            else:
                                status = "failed"
                                failure_reason = "Wrong answer, no improvement possible"
                                break
                    else:
                        logger.warning(f"[{self.request_id}] Insufficient time for re-submission")
                        status = "failed"
                        failure_reason = "Insufficient time to retry"
                        break
                    
            except Exception as e:
                logger.error(f"[{self.request_id}] Error in solve loop: {e}", exc_info=True)
                status = "failed"
                failure_reason = str(e)
                break
        
        return {
            "request_id": self.request_id,
            "attempts": attempts,
            "status": status,
            "reason": failure_reason,
            "time_remaining": self._time_remaining()
        }
    
    async def _extract_task(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract task info from quiz page using Playwright."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                logger.info(f"[{self.request_id}] Loading {url}")
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)  # Extra wait for JS rendering
                
                html_content = await page.content()
                task_text = await self._extract_instructions(page)
                submit_url = await self._extract_submit_url(page, html_content)
                schema = await self._extract_schema(page, html_content)
                files = await self._extract_and_download_files(page)
                
                task_data = {
                    "url": url,
                    "task_text": task_text,
                    "page_html": html_content,
                    "submit_url": submit_url,
                    "submit_schema": schema,
                    "files_data": files,
                }
                
                logger.info(f"[{self.request_id}] Parsed page. Submit URL: {submit_url}")
                if not submit_url:
                    logger.debug(f"[{self.request_id}] Page title: {await page.title()}")
                    logger.debug(f"[{self.request_id}] Page URL: {page.url}")
                    logger.debug(f"[{self.request_id}] First 500 chars of task_text: {task_text[:500]}")
                return task_data
                
            except Exception as e:
                logger.error(f"[{self.request_id}] Error extracting task: {e}", exc_info=True)
                return None
            finally:
                await context.close()
                await browser.close()
    
    async def _extract_instructions(self, page) -> str:
        """Extract visible task instructions from page."""
        try:
            # First try getting text content
            text = await page.inner_text("body")
            if text and len(text.strip()) > 10:
                return text[:3000]
            
            # If no text (canvas-based content), extract from page source/scripts
            html_content = await page.content()
            
            # Look for instructions in script tags
            script_matches = re.findall(r'(?:const|let|var)\s+(?:lines|instructions|task|puzzle)?\s*=\s*\[([\s\S]*?)\];', html_content, re.IGNORECASE)
            if script_matches:
                instructions = script_matches[0]
                # Clean up and return
                return instructions[:3000]
            
            # Look for console.log statements that describe the task
            log_matches = re.findall(r'console\.log\s*\(\s*{([^}]+)}\s*\)', html_content)
            if log_matches:
                return log_matches[0][:3000]
            
            # Fall back to HTML
            return html_content[:3000]
        except:
            return ""
    
    async def _extract_submit_url(self, page, html_content: str = "") -> Optional[str]:
        """Extract submit endpoint from page."""
        try:
            # Get current page URL to derive submit endpoint
            current_url = str(page.url)
            base_url = current_url.rsplit('/', 1)[0]  # Get base URL
            domain = '/'.join(current_url.split('/')[:3])  # Get domain
            
            # 1. Look for forms with action attribute
            forms = await page.query_selector_all("form")
            if forms:
                action = await forms[0].get_attribute("action")
                if action:
                    url = urljoin(current_url, action)
                    logger.info(f"[{self.request_id}] Found submit URL in form: {url}")
                    return url
            
            # 2. Look in scripts for POST endpoints (fetch/axios/jQuery)
            scripts = await page.query_selector_all("script")
            for script in scripts:
                content = await script.inner_text()
                
                # Match various patterns: fetch(...), $.post(...), axios.post(...)
                patterns = [
                    r'(?:fetch|post)\s*\(\s*["\']?(https?://[^\s"\'\)]+)',
                    r'(?:fetch|post)\s*\(\s*["\']?(https?://[^\s"\'\,]+)',
                    r'url\s*:\s*["\']?(https?://[^\s"\'\}]+)',
                    r'endpoint\s*:\s*["\']?(https?://[^\s"\'\}]+)',
                    r'action\s*:\s*["\']?(https?://[^\s"\'\}]+)',
                    r'submit.*?url\s*:\s*["\']?(https?://[^\s"\'\}]+)',
                ]
                
                for pattern in patterns:
                    urls = re.findall(pattern, content, re.IGNORECASE)
                    if urls:
                        for url in urls:
                            if url and len(url) < 300:
                                logger.info(f"[{self.request_id}] Found submit URL in script: {url}")
                                return url
            
            # 3. Look in HTML content for action attributes or data attributes
            if html_content:
                # Look for data-submit or data-url attributes
                action_urls = re.findall(r'(?:data-submit|data-action|action)=["\']?(https?://[^\s"\']+)', html_content, re.IGNORECASE)
                if action_urls:
                    logger.info(f"[{self.request_id}] Found submit URL in HTML attributes: {action_urls[0]}")
                    return action_urls[0]
            
            # 4. Look in page text for URLs with submit-like keywords
            page_text = await page.inner_text("body")
            urls = re.findall(r'https?://[^\s\n"\'<>]+', page_text)
            if urls:
                for url in urls:
                    if any(x in url.lower() for x in ['/submit', '/api', '/answer', '/check', '/solve', '/process']):
                        logger.info(f"[{self.request_id}] Found submit URL in page text: {url}")
                        return url
            
            # 5. Look in hidden divs/elements
            hidden_elements = await page.query_selector_all("[style*='display:none'], [hidden], .hidden, [data-submit]")
            for elem in hidden_elements:
                try:
                    text_content = await elem.inner_text()
                    urls = re.findall(r'https?://[^\s\n"\'<>]+', text_content)
                    if urls and any(x in urls[0].lower() for x in ['/submit', '/api']):
                        logger.info(f"[{self.request_id}] Found submit URL in hidden element: {urls[0]}")
                        return urls[0]
                except:
                    pass
            
            # 6. Look in code/pre blocks
            pre_tags = await page.query_selector_all("pre, code")
            for tag in pre_tags:
                content = await tag.inner_text()
                urls = re.findall(r'https?://[^\s\n"\'<>]+', content)
                if urls:
                    for url in urls:
                        if any(x in url.lower() for x in ['/submit', '/api', '/check', '/solve']):
                            logger.info(f"[{self.request_id}] Found submit URL in pre/code: {url}")
                            return url
            
            # 7. Extract all URLs and look for the most likely submit endpoint
            if page_text:
                all_urls = re.findall(r'https?://[^\s\n"\'<>]+', page_text)
                if all_urls:
                    # Prefer URLs from the same domain as the current page
                    current_domain = str(page.url).split('/')[2]
                    domain_urls = [u for u in all_urls if current_domain in u]
                    if domain_urls:
                        logger.info(f"[{self.request_id}] Found domain-matching URL: {domain_urls[0]}")
                        return domain_urls[0]
                    
                    # If no domain match, take first HTTPS URL
                    https_urls = [u for u in all_urls if u.startswith('https')]
                    if https_urls:
                        logger.info(f"[{self.request_id}] Found HTTPS URL: {https_urls[0]}")
                        return https_urls[0]
            
            # 8. Last resort: Assume /submit endpoint on same domain
            # This is based on the spec which says pages "always include submit URL"
            # If we can't find it explicitly, assume it's the standard /submit endpoint
            assumed_submit_url = f"{domain}/submit"
            logger.info(f"[{self.request_id}] No explicit submit URL found, assuming: {assumed_submit_url}")
            return assumed_submit_url
            
        except Exception as e:
            logger.error(f"[{self.request_id}] Error extracting submit URL: {e}", exc_info=True)
            return None
    
    async def _extract_schema(self, page, html_content: str = "") -> Dict[str, Any]:
        """Extract submission schema from page."""
        try:
            scripts = await page.query_selector_all("script")
            for script in scripts:
                content = await script.inner_text()
                if '"email"' in content and '"answer"' in content:
                    try:
                        json_str = content[max(0, content.find('{')):]
                        json_obj = json.loads(json_str[:json_str.find('}')+1])
                        return json_obj
                    except:
                        pass
            
            if html_content and '"email"' in html_content:
                match = re.search(r'\{[^{}]*"email"[^{}]*\}', html_content)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except:
                        pass
            
            return {"email": "", "secret": "", "url": "", "answer": ""}
        except:
            return {"email": "", "secret": "", "url": "", "answer": ""}
    
    async def _extract_and_download_files(self, page) -> Dict[str, str]:
        """Download files from page links."""
        files = {}
        try:
            async with httpx.AsyncClient() as client:
                links = await page.query_selector_all("a[href]")
                for link in links[:10]:
                    if self._is_timeout():
                        break
                        
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    
                    file_url = urljoin(str(page.url), href)
                    if any(file_url.lower().endswith(ext) for ext in ['.pdf', '.csv', '.json', '.txt', '.png', '.jpg', '.xlsx']):
                        try:
                            resp = await client.get(file_url, timeout=15, follow_redirects=True)
                            if resp.status_code == 200 and len(resp.content) < self.max_file_size:
                                file_path = os.path.join(self.temp_dir, Path(file_url).name)
                                with open(file_path, 'wb') as f:
                                    f.write(resp.content)
                                files[Path(file_url).name] = file_path
                                logger.info(f"[{self.request_id}] Downloaded {Path(file_url).name}")
                        except Exception as e:
                            logger.debug(f"[{self.request_id}] Failed to download {file_url}: {e}")
        except Exception as e:
            logger.debug(f"[{self.request_id}] Error extracting files: {e}")
        
        return files
    
    async def _compute_answer(self, task_data: Dict[str, Any], retry: bool = False) -> Optional[Union[str, int, float, bool, dict]]:
        """Compute answer - can be string, number, boolean, or JSON."""
        try:
            task_text = task_data.get("task_text", "")
            page_html = task_data.get("page_html", "")
            files = task_data.get("files_data", {})
            
            # Look for hidden elements
            hidden_match = re.search(r'class=["\']?hidden["\']?[^>]*>([^<]+)<', page_html)
            if hidden_match:
                hidden_text = hidden_match.group(1).strip()
                logger.info(f"[{self.request_id}] Found hidden element: {hidden_text}")
                
                if "reverse" in task_text.lower() or "un-reverse" in task_text.lower():
                    return hidden_text[::-1]
                return hidden_text
            
            # Parse file contents
            file_contents = {}
            for filename, filepath in files.items():
                try:
                    if filename.endswith('.csv'):
                        df = pd.read_csv(filepath)
                        file_contents[filename] = df.to_string()
                    elif filename.endswith('.json'):
                        with open(filepath) as f:
                            file_contents[filename] = json.dumps(json.load(f), indent=2)
                    elif filename.endswith('.xlsx'):
                        df = pd.read_excel(filepath)
                        file_contents[filename] = df.to_string()
                    else:
                        with open(filepath, 'r', errors='ignore') as f:
                            file_contents[filename] = f.read(2000)
                except Exception as e:
                    logger.debug(f"[{self.request_id}] Error parsing {filename}: {e}")
            
            # Use LLM to compute answer
            answer = await self.llm_helper.compute_answer(
                instructions=task_text,
                file_contents=file_contents,
                page_html=page_html,
                retry=retry
            )
            
            return answer
        except Exception as e:
            logger.error(f"[{self.request_id}] Error computing answer: {e}", exc_info=True)
            return None
    
    def _format_answer(self, answer: Any) -> Any:
        """Format answer to proper type (number, string, boolean, JSON)."""
        if answer is None:
            return ""
        
        # Try to parse as number
        if isinstance(answer, str):
            # Try int
            try:
                return int(answer)
            except:
                pass
            
            # Try float
            try:
                return float(answer)
            except:
                pass
            
            # Check for boolean
            if answer.lower() in ['true', 'yes']:
                return True
            if answer.lower() in ['false', 'no']:
                return False
            
            # Try JSON
            if answer.strip().startswith('{') or answer.strip().startswith('['):
                try:
                    return json.loads(answer)
                except:
                    pass
            
            # Return as string
            return answer
        
        return answer
    
    async def _submit_answer(self, task_data: Dict[str, Any], answer: Any) -> Optional[Dict[str, Any]]:
        """Submit answer to quiz endpoint."""
        submit_url = task_data.get("submit_url")
        if not submit_url:
            # This should not happen now, but keep as safety check
            logger.error(f"[{self.request_id}] No submit URL in task data")
            return None
        
        schema = task_data.get("submit_schema", {})
        payload = {}
        
        if "email" in schema or not schema:
            payload["email"] = self.email
        if "secret" in schema or not schema:
            payload["secret"] = self.secret
        if "url" in schema:
            payload["url"] = task_data.get("url", "")
        if "answer" in schema or not schema:
            payload["answer"] = answer
        
        payload_json = json.dumps(payload)
        if len(payload_json.encode()) > self.max_payload_size:
            logger.error(f"[{self.request_id}] Payload too large: {len(payload_json.encode())} bytes")
            return None
        
        try:
            logger.info(f"[{self.request_id}] Submitting to {submit_url}")
            logger.info(f"[{self.request_id}] Payload: {payload}")
            
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(submit_url, json=payload)
                logger.info(f"[{self.request_id}] Submit response status: {resp.status_code}")
                logger.info(f"[{self.request_id}] Submit response body: {resp.text[:500]}")
                
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except:
                        return {"correct": False}
                return None
        except Exception as e:
            logger.error(f"[{self.request_id}] Error submitting answer: {e}", exc_info=True)
            return None