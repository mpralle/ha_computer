"""Summariser Agent: Converts execution reports to user-friendly responses."""
from __future__ import annotations

import json
import logging
from typing import Any

from .llm_client import LlamaCppClient

_LOGGER = logging.getLogger(__name__)

# System prompt for the Summariser Agent
SUMMARISER_SYSTEM_PROMPT = """You are a helpful assistant that summarizes what actions were completed.

RULES:
1. Respond in the same language as the user
2. Be concise (1-2 sentences max)
3. ONLY mention what actually succeeded based on the execution report
4. If something failed, mention it clearly
5. Do NOT hallucinate or claim actions that weren't in the report

EXAMPLES:

User: "Schalte Regallampe und Schranklampe an"
Report: {"results": [{"entity": "light.regallampe", "success": true}, {"entity": "light.schranklampe", "success": true}]}
Response: "Ich habe die Regallampe und Schranklampe eingeschaltet."

User: "Schalte Regallampe und Schranklampe an"
Report: {"results": [{"entity": "light.regallampe", "success": true}, {"entity": "light.schranklampe", "success": false, "error": "Entity not found"}]}
Response: "Ich habe die Regallampe eingeschaltet, aber ich konnte die Schranklampe nicht finden."

User: "Add milk and bread to shopping list"
Report: {"results": [{"item": "Milk", "success": true}, {"item": "Bread", "success": true}]}
Response: "I've added Milk and Bread to your shopping list."

User: "Packe Käse und Wein auf die Einkaufsliste"
Report: {"results": [{"item": "Käse", "success": true}, {"item": "Wein", "success": true}]}
Response: "Ich habe Käse und Wein auf die Einkaufsliste gepackt."
"""


class SummariserAgent:
    """
    Agent that converts execution reports into natural language responses.
    
    This is the final agent in the pipeline, creating user-friendly summaries.
    """
    
    def __init__(self, llm_client: LlamaCppClient) -> None:
        """Initialize the Summariser Agent."""
        self.llm_client = llm_client
    
    async def summarise(
        self,
        user_utterance: str,
        execution_report: dict[str, Any],
    ) -> str:
        """
        Generate user-friendly summary from execution report.
        
        Args:
            user_utterance: The original user request
            execution_report: Structured report from Executor
        
        Returns:
            Natural language summary of what was done
        """
        # Compress report to only essential info
        compressed = self._compress_report(execution_report)
        
        messages = [
            {"role": "system", "content": SUMMARISER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"User request: {user_utterance}\n\nExecution report: {json.dumps(compressed, ensure_ascii=False)}",
            },
        ]
        
        _LOGGER.debug("Summarising execution report")
        
        try:
            response = await self.llm_client.chat(
                messages,
                temperature=0.1,
                max_tokens=100,
                timeout=30,
            )
            
            if not response:
                response = self._fallback_summary(execution_report)
            
        except Exception as err:
            _LOGGER.error("Summariser failed: %s", err)
            response = self._fallback_summary(execution_report)
        
        _LOGGER.info("Summary: %s", response)
        return response
    
    def _compress_report(self, report: dict[str, Any]) -> dict[str, Any]:
        """Compress report to only show key info."""
        return {
            "successful": report.get("successful_operations", 0),
            "failed": report.get("failed_operations", 0),
            "details": [
                {
                    "type": r.get("task_type"),
                    "operation": r.get("operation"),
                    "entity": r.get("entity"),
                    "item": r.get("item"),
                    "success": r.get("success"),
                    "error": r.get("error"),
                }
                for r in report.get("results", [])
            ],
        }
    
    def _fallback_summary(self, report: dict[str, Any]) -> str:
        """Generate a simple fallback summary if LLM fails."""
        successful = report.get("successful_operations", 0)
        failed = report.get("failed_operations", 0)
        
        if successful > 0 and failed == 0:
            return f"Done! Completed {successful} action(s) successfully."
        elif successful > 0 and failed > 0:
            return f"Completed {successful} action(s), but {failed} failed."
        elif failed > 0:
            return f"Sorry, {failed} action(s) failed."
        else:
            return "No actions were performed."
