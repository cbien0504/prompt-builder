import os
from typing import TypedDict
import requests

class ParaphrasedQuery(TypedDict):
    original: str
    paraphrased: str
    actions: list[str]


class LLMQueryParaphraser:
    DEFAULT_MODEL = "HuggingFaceTB/SmolLM2-1.7B-Instruct"
    
    SYSTEM_PROMPT = """You are a helpful assistant that reformulates developer queries into clear, actionable statements.

Your task:
1. Rephrase the user's query to be more specific and clear
2. Break down what needs to be done into concrete action steps

Respond in JSON format:
{
  "paraphrased": "Clear, specific reformulation of the query",
  "actions": ["specific action 1", "specific action 2", "specific action 3"]
}

Keep the paraphrased query concise but specific. List 3-5 concrete actions."""

    def __init__(self, model: str | None = None):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = os.getenv("HF_TOKEN")
        
        if not self.api_key:
            raise ValueError("HF_TOKEN environment variable not set")
        
        self.api_base = "https://api-inference.huggingface.co/models"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def _call_llm(self, prompt: str, max_tokens: int = 250) -> str:
        """Call HuggingFace Inference API."""
        url = f"{self.api_base}/{self.model}"
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": 0.3,
                "do_sample": True,
                "return_full_text": False,
            },
            "options": {
                "wait_for_model": True,
            },
        }
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse response
            if isinstance(data, list) and data:
                return data[0].get("generated_text", "").strip()
            elif isinstance(data, dict):
                return data.get("generated_text", "").strip()
            
            return ""
            
        except Exception as e:
            print(f"LLM API error: {e}")
            return ""
    
    def paraphrase_query(self, query: str) -> ParaphrasedQuery:
        """
        Paraphrase a user query into a clear, actionable statement.
        
        Args:
            query: The user's original query
            
        Returns:
            ParaphrasedQuery dict with original, paraphrased, and actions
        """
        if not query or not query.strip():
            return {
                'original': query,
                'paraphrased': 'No query provided',
                'actions': []
            }
        
        # Construct prompt
        prompt = f"""{self.SYSTEM_PROMPT}

User query: "{query}"

JSON response:"""
        
        # Call LLM
        result = self._call_llm(prompt, max_tokens=250)
        
        # Try to parse JSON response
        try:
            import json
            
            # Extract JSON from response
            json_start = result.find('{')
            json_end = result.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = result[json_start:json_end]
                parsed = json.loads(json_str)
                
                return {
                    'original': query,
                    'paraphrased': parsed.get('paraphrased', query),
                    'actions': parsed.get('actions', [])
                }
        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON parse error: {e}")
            print(f"Raw response: {result}")
        
        # Fallback: use simple paraphrasing
        return self._create_fallback_paraphrase(query)
    
    def _create_fallback_paraphrase(self, query: str) -> ParaphrasedQuery:
        """Create a fallback paraphrase when LLM fails."""
        # Simple rule-based paraphrasing
        query_lower = query.lower().strip()
        
        # Common patterns
        if any(word in query_lower for word in ['why', 'broken', 'not working', 'error', 'bug']):
            paraphrased = f"Investigate and fix the issue: {query}"
            actions = [
                "Identify the root cause of the problem",
                "Review error messages and logs",
                "Test potential solutions",
                "Verify the fix works correctly"
            ]
        elif any(word in query_lower for word in ['how', 'what', 'explain']):
            paraphrased = f"Provide a clear explanation of: {query}"
            actions = [
                "Break down the concept step by step",
                "Explain key components and their relationships",
                "Provide examples for better understanding",
                "Clarify any complex or ambiguous parts"
            ]
        elif any(word in query_lower for word in ['optimize', 'faster', 'slow', 'performance']):
            paraphrased = f"Improve the performance of: {query}"
            actions = [
                "Profile and identify performance bottlenecks",
                "Optimize algorithms and data structures",
                "Reduce unnecessary computations",
                "Benchmark and verify improvements"
            ]
        elif any(word in query_lower for word in ['create', 'add', 'build', 'implement', 'new']):
            paraphrased = f"Implement the requested functionality: {query}"
            actions = [
                "Design the solution architecture",
                "Write clean and maintainable code",
                "Add proper error handling",
                "Test the implementation thoroughly"
            ]
        elif any(word in query_lower for word in ['refactor', 'clean', 'improve', 'rewrite']):
            paraphrased = f"Refactor and improve: {query}"
            actions = [
                "Identify areas needing improvement",
                "Apply clean code principles",
                "Maintain existing functionality",
                "Improve readability and maintainability"
            ]
        else:
            paraphrased = f"Address the request: {query}"
            actions = [
                "Analyze the requirements",
                "Plan the approach",
                "Implement the solution",
                "Verify it meets the needs"
            ]
        
        return {
            'original': query,
            'paraphrased': paraphrased,
            'actions': actions
        }
    
    def paraphrase_to_string(self, query: str) -> str:
        """
        Paraphrase query and return as formatted string.
        
        Args:
            query: The user's query string
            
        Returns:
            Formatted string with paraphrased query and actions
        """
        result = self.paraphrase_query(query)
        
        output = f"""Original: {result['original']}

Paraphrased: {result['paraphrased']}

Actions to take:"""
        
        for i, action in enumerate(result['actions'], 1):
            output += f"\n{i}. {action}"
        
        return output


# Singleton instance
_paraphraser = None


def _get_paraphraser() -> LLMQueryParaphraser:
    """Get or create singleton paraphraser instance."""
    global _paraphraser
    if _paraphraser is None:
        _paraphraser = LLMQueryParaphraser()
    return _paraphraser


def paraphrase_query(query: str, model: str | None = None) -> ParaphrasedQuery:
    """
    Paraphrase a user query into a clear, actionable statement.
    
    Args:
        query: The user's natural language query
        model: Optional HuggingFace model name
        
    Returns:
        ParaphrasedQuery dict with:
        - original: The original query
        - paraphrased: Clear reformulation of the query
        - actions: List of specific actions to take
        
    Example:
        >>> result = paraphrase_query("Why isn't this working?")
        >>> print(result['paraphrased'])
        'Investigate and resolve the issue preventing the code from functioning correctly'
        >>> print(result['actions'])
        ['Check error messages', 'Review recent changes', 'Test with different inputs']
    """
    if model:
        paraphraser = LLMQueryParaphraser(model)
        return paraphraser.paraphrase_query(query)
    return _get_paraphraser().paraphrase_query(query)


def paraphrase_to_string(query: str, model: str | None = None) -> str:
    """
    Paraphrase query and return as formatted string.
    
    Args:
        query: The user's natural language query
        model: Optional HuggingFace model name
        
    Returns:
        Formatted string with paraphrased query and actions
        
    Example:
        >>> print(paraphrase_to_string("Make this faster"))
        Original: Make this faster
        
        Paraphrased: Optimize the code to improve execution speed and performance
        
        Actions to take:
        1. Profile the code to identify bottlenecks
        2. Optimize algorithms and data structures
        3. Reduce unnecessary operations
        4. Benchmark performance improvements
    """
    if model:
        paraphraser = LLMQueryParaphraser(model)
        return paraphraser.paraphrase_to_string(query)
    return _get_paraphraser().paraphrase_to_string(query)


# Example usage
if __name__ == "__main__":
    test_queries = [
        "Why is this function returning None?",
        "How does authentication work here?",
        "This code is messy",
        "Make the database queries faster",
        "Add password reset",
        "Compare REST vs GraphQL",
        "Check for security issues",
        "The login isn't working",
        "Explain this algorithm",
        "Refactor the user service",
    ]
    
    print("LLM-Based Query Paraphrasing\n")
    print("=" * 80)
    print(f"Model: {LLMQueryParaphraser.DEFAULT_MODEL}\n")
    
    for query in test_queries:
        print("=" * 80)
        print(f"Original: {query}\n")
        
        try:
            result = paraphrase_query(query)
            print(f"Paraphrased: {result['paraphrased']}\n")
            print("Actions:")
            for i, action in enumerate(result['actions'], 1):
                print(f"  {i}. {action}")
            print()
        except Exception as e:
            print(f"Error: {e}\n")