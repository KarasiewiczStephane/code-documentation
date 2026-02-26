"""Claude API client with rate limiting, retries, and cost estimation.

Wraps the Anthropic SDK to provide a high-level interface for
generating documentation, with built-in token counting, cost
estimation, rate limiting, and exponential backoff retry logic.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import anthropic

from src.utils.config import APIConfig

logger = logging.getLogger(__name__)

# Pricing per million tokens (approximate, as of 2025)
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
}

# Fallback pricing if model not in the map
_DEFAULT_PRICING = {"input": 3.0, "output": 15.0}


@dataclass
class TokenUsage:
    """Token usage statistics for a single API call.

    Attributes:
        input_tokens: Number of tokens in the prompt.
        output_tokens: Number of tokens in the response.
    """

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed."""
        return self.input_tokens + self.output_tokens


@dataclass
class CostEstimate:
    """Estimated API cost for a generation request.

    Attributes:
        input_tokens: Estimated input token count.
        output_tokens: Estimated output token count.
        input_cost_usd: Estimated input cost in USD.
        output_cost_usd: Estimated output cost in USD.
        total_cost_usd: Estimated total cost in USD.
        model: Model used for the estimate.
    """

    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    model: str


@dataclass
class GenerationResult:
    """Result of an LLM generation call.

    Attributes:
        content: The generated text content.
        usage: Token usage statistics.
        model: Model that produced the result.
        stop_reason: Reason the generation stopped.
    """

    content: str
    usage: TokenUsage
    model: str
    stop_reason: Optional[str] = None


class LLMClient:
    """Client for the Anthropic Claude API with rate limiting and retries.

    Provides methods for generating text, counting tokens, and
    estimating costs. Implements rate limiting to stay within API
    quotas and exponential backoff for transient errors.
    """

    def __init__(self, config: Optional[APIConfig] = None) -> None:
        """Initialize the LLM client.

        Args:
            config: API configuration. Uses defaults if not provided.

        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set.
        """
        self.config = config or APIConfig()
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._client: Optional[anthropic.Anthropic] = None
        self._last_request_time: float = 0.0
        self._request_interval: float = 60.0 / max(self.config.rate_limit_rpm, 1)
        self._total_usage = TokenUsage()

    @property
    def client(self) -> anthropic.Anthropic:
        """Lazily initialize the Anthropic client.

        Returns:
            An authenticated Anthropic client instance.

        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set.
        """
        if self._client is None:
            if not self._api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable is not set. "
                    "Set it before making API calls."
                )
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> GenerationResult:
        """Generate text using the Claude API.

        Sends a prompt to Claude and returns the generated response.
        Applies rate limiting and retry logic automatically.

        Args:
            prompt: The user message prompt.
            system: Optional system prompt for context.
            max_tokens: Maximum tokens to generate. Uses config default.
            temperature: Sampling temperature. Uses config default.

        Returns:
            A GenerationResult with the generated content and usage.

        Raises:
            ValueError: If the API key is not set.
            anthropic.APIError: If the API call fails after all retries.
        """
        self._apply_rate_limit()

        messages = [{"role": "user", "content": prompt}]
        kwargs: dict = {
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature
            if temperature is not None
            else self.config.temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = self._call_with_retry(**kwargs)

        content = ""
        if response.content:
            content = response.content[0].text

        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        self._total_usage.input_tokens += usage.input_tokens
        self._total_usage.output_tokens += usage.output_tokens

        logger.info(
            "Generated %d tokens (input: %d, output: %d)",
            usage.total_tokens,
            usage.input_tokens,
            usage.output_tokens,
        )

        return GenerationResult(
            content=content,
            usage=usage,
            model=response.model,
            stop_reason=response.stop_reason,
        )

    def estimate_cost(
        self,
        prompt: str,
        estimated_output_tokens: int = 1000,
        model: Optional[str] = None,
    ) -> CostEstimate:
        """Estimate the cost of a generation request.

        Uses approximate token counting to estimate costs without
        actually making an API call.

        Args:
            prompt: The prompt text to estimate.
            estimated_output_tokens: Expected output token count.
            model: Model to use for pricing. Uses config default.

        Returns:
            A CostEstimate with token counts and costs.
        """
        model_name = model or self.config.model
        input_tokens = self.count_tokens(prompt)
        pricing = _MODEL_PRICING.get(model_name, _DEFAULT_PRICING)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (estimated_output_tokens / 1_000_000) * pricing["output"]

        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=estimated_output_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=input_cost + output_cost,
            model=model_name,
        )

    def count_tokens(self, text: str) -> int:
        """Estimate the token count of a text string.

        Uses a simple heuristic (4 characters per token) for fast
        estimation without API calls.

        Args:
            text: Text to count tokens for.

        Returns:
            Estimated token count.
        """
        # Rough approximation: ~4 chars per token for English text
        return max(1, len(text) // 4)

    @property
    def total_usage(self) -> TokenUsage:
        """Get the cumulative token usage across all calls.

        Returns:
            A TokenUsage with total input and output tokens.
        """
        return self._total_usage

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting by sleeping if necessary."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._request_interval:
            sleep_time = self._request_interval - elapsed
            logger.debug("Rate limiting: sleeping %.2f seconds", sleep_time)
            time.sleep(sleep_time)
        self._last_request_time = time.monotonic()

    def _call_with_retry(self, **kwargs: object) -> anthropic.types.Message:
        """Make an API call with exponential backoff retry logic.

        Args:
            **kwargs: Arguments to pass to the Anthropic messages.create call.

        Returns:
            The API response Message.

        Raises:
            anthropic.APIError: If all retries are exhausted.
        """
        last_error: Optional[Exception] = None
        base_delay = self.config.retry_base_delay

        for attempt in range(self.config.retry_max_attempts):
            try:
                return self.client.messages.create(**kwargs)
            except anthropic.RateLimitError as e:
                last_error = e
                delay = base_delay * (2**attempt)
                logger.warning(
                    "Rate limited (attempt %d/%d), retrying in %.1f seconds",
                    attempt + 1,
                    self.config.retry_max_attempts,
                    delay,
                )
                time.sleep(delay)
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        "Server error %d (attempt %d/%d), retrying in %.1f seconds",
                        e.status_code,
                        attempt + 1,
                        self.config.retry_max_attempts,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    raise

        raise last_error  # type: ignore[misc]
