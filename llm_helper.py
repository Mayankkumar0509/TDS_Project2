import re
import json
import logging
from typing import Optional, Dict, Any
import asyncio

from config import AIML_API_KEY, AIML_BASE_URL, AIML_MODEL

logger = logging.getLogger(__name__)

class LLMHelper:
    """Wrapper for AIML LLM calls with heuristic fallbacks."""
    
    def __init__(self):
        self.api_key = AIML_API_KEY
        self.base_url = AIML_BASE_URL
        self.model = AIML_MODEL
        self.use_llm = bool(self.api_key)
        
        if self.use_llm:
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
                logger.info(f"✅ AIML LLM initialized: {self.model} at {self.base_url}")
            except Exception as e:
                logger.error(f"Failed to initialize AIML client: {e}")
                self.use_llm = False
        else:
            logger.warning("⚠️ AIML_API_KEY not set. Using heuristic fallbacks.")
    
    async def analyze_task(self, task_text: str, context: str = "") -> Dict[str, Any]:
        """
        Analyze task instructions and extract key requirements.
        
        Args:
            task_text: The task instruction text
            context: Additional context (data preview, etc.)
        
        Returns:
            Dict with keys: task_type, action, expected_format
        """
        if self.use_llm:
            return await self._call_llm_analyze(task_text, context)
        else:
            return self._heuristic_analyze(task_text, context)
    
    async def solve_task(self, task_text: str, data: str, 
                        task_type: Optional[str] = None) -> Any:
        """
        Solve a specific task given task text and data.
        
        Args:
            task_text: Task instruction
            data: Data content (CSV, JSON, text, etc.)
            task_type: Hint about task type (sum, count, extract, etc.)
        
        Returns:
            The computed/inferred answer
        """
        if self.use_llm:
            return await self._call_llm_solve(task_text, data)
        else:
            return self._heuristic_solve(task_text, data, task_type)
    
    async def _call_llm_analyze(self, task_text: str, context: str) -> Dict[str, Any]:
        """Call AIML to analyze task."""
        try:
            prompt = f"""Analyze this task and return a JSON response with the following structure:
{{
    "task_type": "sum|count|average|extract|calculation|other",
    "action": "What should be done",
    "expected_format": "The format of the answer (number, string, list, etc.)"
}}

Task: {task_text}
Context: {context}

Return ONLY valid JSON, no other text."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                logger.info(f"LLM analysis: {result}")
                return result
            else:
                logger.warning(f"Could not parse LLM response: {response_text}")
                return self._heuristic_analyze(task_text, context)
        
        except Exception as e:
            logger.error(f"LLM analyze error: {e}")
            return self._heuristic_analyze(task_text, context)
    
    async def _call_llm_solve(self, task_text: str, data: str) -> Any:
        """Call AIML to solve the task."""
        try:
            # Truncate data if too large
            data_truncated = data[:8000] if len(data) > 8000 else data
            
            prompt = f"""You are an expert data analyst. Solve this task based on the provided data.

Task: {task_text}

Data:
{data_truncated}

Provide a clear, concise answer. If the answer is a number, return just the number.
If it's a list, return a JSON array. If it's text, return the text.
Return ONLY the answer, nothing else."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            answer_text = response.choices[0].message.content.strip()
            logger.info(f"LLM solved answer: {answer_text}")
            
            # Try to parse as JSON/number if applicable
            try:
                if answer_text.startswith('[') or answer_text.startswith('{'):
                    return json.loads(answer_text)
                elif answer_text.replace('.', '', 1).isdigit():
                    return float(answer_text) if '.' in answer_text else int(answer_text)
            except:
                pass
            
            return answer_text
        
        except Exception as e:
            logger.error(f"LLM solve error: {e}")
            return self._heuristic_solve(task_text, data)
    
    def _heuristic_analyze(self, task_text: str, context: str) -> Dict[str, Any]:
        """Fallback heuristic task analysis."""
        task_lower = task_text.lower()
        
        task_type = "unknown"
        if re.search(r"sum|total|add", task_lower):
            task_type = "sum"
        elif re.search(r"count|how many|number", task_lower):
            task_type = "count"
        elif re.search(r"average|mean|median", task_lower):
            task_type = "average"
        elif re.search(r"extract|find|list", task_lower):
            task_type = "extract"
        
        return {
            "task_type": task_type,
            "action": "analyze_compute",
            "expected_format": "json"
        }
    
    def _heuristic_solve(self, task_text: str, data: str, 
                        task_type: Optional[str] = None) -> Any:
        """Fallback heuristic task solving."""
        try:
            import pandas as pd
            
            # Try parsing as JSON
            try:
                parsed = json.loads(data)
                if isinstance(parsed, list) and parsed:
                    if isinstance(parsed[0], dict):
                        df = pd.DataFrame(parsed)
                    else:
                        df = pd.Series(parsed)
                else:
                    df = pd.Series([parsed])
            except:
                # Try CSV-like format
                df = pd.read_csv(__import__('io').StringIO(data))
            
            task_lower = task_text.lower()
            
            # Sum heuristic
            if re.search(r"sum|total|add", task_lower):
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    return int(df[numeric_cols[0]].sum())
            
            # Count heuristic
            if re.search(r"count|how many", task_lower):
                return len(df)
            
            # Average heuristic
            if re.search(r"average|mean", task_lower):
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    return round(float(df[numeric_cols[0]].mean()), 2)
            
            # Extract heuristic - return first few rows
            if re.search(r"extract|find|list", task_lower):
                return df.head(3).to_dict(orient='records')
            
            # Default: return summary
            return {"rows": len(df), "columns": list(df.columns)}
        
        except Exception as e:
            logger.warning(f"Heuristic solve failed: {e}")
            return {"error": str(e), "data_length": len(data)}

llm_helper = LLMHelper()