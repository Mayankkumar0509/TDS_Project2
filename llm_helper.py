import logging
import json
import re
import os
from typing import Dict

logger = logging.getLogger(__name__)

class LLMHelper:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.use_llm = bool(self.api_key)
    
    async def compute_answer(self, instructions: str, file_contents: Dict[str, str], page_html: str = "", retry: bool = False) -> str:
        """
        Compute answer using LLM if available, otherwise use heuristics.
        Answer can be: boolean, number, string, base64 URI, or JSON object.
        """
        if self.use_llm:
            return await self._call_llm(instructions, file_contents, page_html, retry)
        else:
            return self._heuristic_answer(instructions, file_contents, page_html, retry)
    
    async def _call_llm(self, instructions: str, file_contents: Dict[str, str], page_html: str = "", retry: bool = False) -> str:
        """Call OpenAI API - may return number, string, boolean, or JSON."""
        try:
            import httpx
            
            context = f"Instructions: {instructions}\n\n"
            for filename, content in file_contents.items():
                context += f"File: {filename}\n{content}\n\n"
            
            if page_html:
                context += f"Page HTML:\n{page_html[:1500]}\n\n"
            
            system_msg = "You are a data analysis and web scraping expert. Extract the answer as a single value (number, string, boolean, or JSON object). Return ONLY the answer, no explanation."
            if retry:
                system_msg += " This is a retry - the previous answer was wrong. Try a different approach."
            
            payload = {
                "model": "gpt-4-mini",
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": context}
                ],
                "temperature": 0.3 if not retry else 0.7,  # Lower temp for first try, higher for retry
                "max_tokens": 500
            }
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    answer = result["choices"][0]["message"]["content"].strip()
                    return answer
        except Exception as e:
            logger.warning(f"LLM call failed, using heuristics: {e}")
        
        return self._heuristic_answer(instructions, file_contents, page_html, retry)
    
    def _heuristic_answer(self, instructions: str, file_contents: Dict[str, str], page_html: str = "", retry: bool = False) -> str:
        """Fallback heuristic for answer computation."""
        lower_instr = instructions.lower()
        
        # 1. Check for reversed/hidden text patterns
        if "reverse" in lower_instr or "un-reverse" in lower_instr:
            if page_html:
                hidden_match = re.search(r'class=["\']?hidden["\']?[^>]*>([^<]+)<', page_html)
                if hidden_match:
                    hidden_text = hidden_match.group(1).strip()
                    return hidden_text[::-1]
        
        # 2. Look for numbers in file contents
        numbers = []
        for content in file_contents.values():
            nums = re.findall(r'-?\d+\.?\d*', content)
            numbers.extend([float(n) for n in nums])
        
        # 3. Common math patterns
        if "sum" in lower_instr and numbers:
            return str(int(sum(numbers)))
        elif "count" in lower_instr and numbers:
            return str(len(numbers))
        elif "average" in lower_instr and numbers:
            return str(int(sum(numbers) / len(numbers)))
        elif "maximum" in lower_instr or "max" in lower_instr:
            if numbers:
                return str(int(max(numbers)))
        elif "minimum" in lower_instr or "min" in lower_instr:
            if numbers:
                return str(int(min(numbers)))
        
        # 4. Default fallback
        return "42"