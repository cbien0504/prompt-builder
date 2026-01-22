from __future__ import annotations
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from pydantic import BaseModel
import requests

class LLMResponse(BaseModel):
    content: Optional[str] = None
    finish_reason: str
    usage: Optional[Dict[str, int]] = None
    time_taken: float
    error: str | None = None

@dataclass
class LLMConfig:
    api_base: str = "https://huggingface.co/"
    model: str = "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"
    max_tokens: int = 4096
    temperature: float = 0.0
    timeout: int = 30


class HuggingFaceClient:
    
    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self.api_key = os.getenv("HF_TOKEN")
        if not self.api_key:
            raise ValueError("HF_TOKEN environment variable not set")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: List[Dict[str, str]] | None = None,
    ) -> LLMResponse:
        messages = []
        if system_prompt and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message.strip()})
        url = f"{self.config.api_base}/{self.config.model}/v1/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        start_time = time.time()
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            data = response.json()
            if "choices" in data and data["choices"]:
                choice = data["choices"][0]
                message_content = choice.get("message", {}).get("content", "")
                usage = data.get("usage", {})
                
                return LLMResponse(
                    content=message_content.strip(),
                    finish_reason=choice.get("finish_reason", "stop"),
                    usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                    time_taken=time.time() - start_time,
                    error=None,
                )
            else:
                raise RuntimeError(f"Unexpected response format: {data}")
            
        except Exception as e:
            return LLMResponse(
                finish_reason="error",
                time_taken=time.time() - start_time,
                error=str(e),
            )

class MultiPartChatSession:    
    def __init__(self, client: HuggingFaceClient):
        self.client = client
        self.conversation_history: List[Dict[str, str]] = []
    
    def send_part(
        self,
        system_prompt: str,
        human_prompt: str,
        is_first_part: bool = False,
    ) -> LLMResponse:
        if is_first_part:
            self.conversation_history = []
        
        response = self.client.chat(
            system_prompt=system_prompt if is_first_part else "",
            user_message=human_prompt,
            conversation_history=self.conversation_history if not is_first_part else None,
        )
        
        if response.content:
            self.conversation_history.append({"role": "user", "content": human_prompt})
            self.conversation_history.append({"role": "assistant", "content": response.content})
        
        return response
    
    def reset(self):
        self.conversation_history = []


def create_client(config: LLMConfig | None = None) -> HuggingFaceClient:
    return HuggingFaceClient(config)