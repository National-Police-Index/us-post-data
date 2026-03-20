import json
import logging
import re
from typing import TypeVar, Type
from pydantic import BaseModel, ValidationError
from openai.lib.azure import AzureOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    retry_if_not_exception_type,
)
from diskcache import Cache
import blake3
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# Azure configuration
AZURE_ENDPOINT = os.getenv('AZURE_ENDPOINT')
AZURE_API_KEY = os.getenv('AZURE_API_KEY')
API_VERSION = os.getenv('API_VERSION')

# Cache setup
CACHE_DIR = "llm-responses.cache"
llm_cache = Cache(CACHE_DIR)

# Available models
AVAILABLE_MODELS = [
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4.1-mini-2025-04-14"
]


class LLM:
    """
    Unified LLM client with built-in structured output support.
    Uses Azure OpenAI and provides structured Pydantic responses.
    """
    
    def __init__(self, model_name="gpt-4.1", base_url=None, max_model_len=8000):
        self.model_name = model_name
        self.client = AzureOpenAI(
            azure_endpoint=AZURE_ENDPOINT,
            api_key=AZURE_API_KEY,
            api_version=API_VERSION
        )
        logger.info(f"Initialized Azure OpenAI client with model {model_name}")
        
    def _run_raw_inference(self, prompt, model=None, max_tokens=4096, temperature=0.1):
        """
        Internal method: Run raw inference using Azure OpenAI.
        Use run_structured_inference() for structured output or run_inference() for text.
        """
        model_to_use = model if model else self.model_name
        
        if model_to_use not in AVAILABLE_MODELS:
            raise ValueError(f"Model {model_to_use} not available. Available: {AVAILABLE_MODELS}")
        
        messages = [{"role": "user", "content": prompt}]
        
        # Create cache key
        serialized = json.dumps(messages, sort_keys=True)
        hash_value = blake3.blake3(serialized.encode()).hexdigest()
        cache_key = f"llm_response-{model_to_use}:{hash_value}"
        
        # Check cache
        # cached_response = llm_cache.get(cache_key)
        # if cached_response:
        #     logger.debug(f"LLM Cache HIT for {cache_key}")
        #     return cached_response
        
        logger.debug(f"LLM Cache MISS for {cache_key}")
        
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=10, max=80),
            before_sleep=before_sleep_log(logger, logging.DEBUG),
        )
        def call_api():
            response = self.client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
            )
            return response.choices[0].message.content
        
        try:
            content = call_api()
            llm_cache.set(cache_key, content)
            return content
        except Exception as e:
            logger.error(f"Azure OpenAI API error: {e}")
            raise RuntimeError(f"Failed to get response from Azure OpenAI: {e}")
    
    def run_inference(self, prompt, model=None, max_tokens=4096, temperature=0.1):
        """
        Run inference and return raw text response.
        
        Args:
            prompt: The prompt to send to the model
            model: Model name to use (optional, defaults to instance model)
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            
        Returns:
            Raw text response from the model
        """
        return self._run_raw_inference(prompt, model, max_tokens, temperature)
    
    def run_structured_inference(self, prompt: str, response_model: Type[T], 
                           model=None, max_tokens=4096, temperature=0.1) -> T:
        model_to_use = model if model else self.model_name
        messages = [{"role": "user", "content": prompt}]
        
        # Cache key
        serialized = json.dumps(messages, sort_keys=True)
        hash_value = blake3.blake3(serialized.encode()).hexdigest()
        cache_key = f"llm_response-{model_to_use}:{hash_value}"
        
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=10, max=80),
            before_sleep=before_sleep_log(logger, logging.DEBUG),
        )
        def call_api():
            completion = self.client.beta.chat.completions.parse(
                model=model_to_use,
                messages=messages,
                response_format=response_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return completion.choices[0].message.parsed
        
        try:
            result = call_api()
            return result
        except Exception as e:
            logger.error(f"Structured inference error: {e}")
            raise ValueError(f"Model returned invalid response: {e}")

    def _clean_schema_response(self, parsed_data: dict) -> dict:
        """
        Clean LLM response that may be wrapped in JSON Schema format.

        Since we show the LLM a JSON Schema, it often returns data wrapped
        in the schema structure with actual values in the 'properties' field.

        Args:
            parsed_data: Parsed JSON dict from LLM

        Returns:
            Cleaned dict with actual data (extracted from 'properties' if needed)
        """
        # If response has 'properties' field, extract the actual data from there
        if "properties" in parsed_data:
            return parsed_data["properties"]

        # Otherwise return as-is
        return parsed_data

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON content from markdown code blocks."""
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        if matches:
            return matches[0].strip()
        
        json_pattern = r'\{.*\}'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        if matches:
            return max(matches, key=len).strip()
        
        raise ValueError("No JSON content found in response")
    
    def test_connection(self):
        """Test the LLM connection with a simple structured response"""
        try:
            from pydantic import BaseModel, Field
            
            class TestResponse(BaseModel):
                message: str = Field(description="A simple test message")
                status: str = Field(description="Status of the test")
            
            response = self.run_structured_inference(
                "Respond with a test message saying you're working and status 'ok'",
                TestResponse
            )
            
            logger.info(f"LLM Test Response: {response.message} (Status: {response.status})")
            return True
            
        except Exception as e:
            logger.error(f"LLM Test Failed: {e}")
            return False


llm = LLM(model_name="gpt-4.1-mini")


# Convenience functions for backward compatibility
def run_structured_inference(prompt: str, response_model: Type[T], **kwargs) -> T:
    """Convenience function for structured inference using the global LLM instance."""
    return llm.run_structured_inference(prompt, response_model, **kwargs)


def run_inference(prompt, model=None, max_tokens=4096, temperature=0.1):
    """
    Run inference and return raw text response.
    This is the main function for text generation.
    """
    return llm.run_inference(prompt, model, max_tokens, temperature)


def test_llm():
    """Test the LLM connection"""
    return llm.test_connection()


if __name__ == "__main__":
    print("Testing Azure OpenAI connection...")
    if test_llm():
        print("✓ Azure OpenAI is working correctly!")
    else:
        print("✗ Azure OpenAI test failed!")