"""Tests for the LLM client with mocked API responses."""

from unittest.mock import MagicMock, patch

import pytest

from src.generators.llm_client import (
    CostEstimate,
    GenerationResult,
    LLMClient,
    TokenUsage,
)
from src.utils.config import APIConfig


@pytest.fixture
def config() -> APIConfig:
    """Create a test API config."""
    return APIConfig(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        temperature=0.1,
        rate_limit_rpm=600,  # High RPM to avoid test delays
        retry_max_attempts=2,
        retry_base_delay=0.01,
    )


@pytest.fixture
def client(config: APIConfig) -> LLMClient:
    """Create an LLMClient with a test config and mock API key."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"}):
        return LLMClient(config=config)


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_total_tokens(self) -> None:
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150

    def test_defaults(self) -> None:
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0


class TestCostEstimate:
    """Tests for CostEstimate dataclass."""

    def test_fields(self) -> None:
        est = CostEstimate(
            input_tokens=1000,
            output_tokens=500,
            input_cost_usd=0.003,
            output_cost_usd=0.0075,
            total_cost_usd=0.0105,
            model="claude-sonnet-4-20250514",
        )
        assert est.input_tokens == 1000
        assert est.total_cost_usd == 0.0105


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_fields(self) -> None:
        result = GenerationResult(
            content="Hello!",
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            model="claude-sonnet-4-20250514",
            stop_reason="end_turn",
        )
        assert result.content == "Hello!"
        assert result.stop_reason == "end_turn"


class TestLLMClientInit:
    """Tests for LLMClient initialization."""

    def test_default_config(self) -> None:
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
            client = LLMClient()
            assert client.config.model == "claude-sonnet-4-20250514"

    def test_custom_config(self, config: APIConfig) -> None:
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
            client = LLMClient(config=config)
            assert client.config.max_tokens == 1024

    def test_missing_api_key_lazy(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            # Remove ANTHROPIC_API_KEY
            import os

            old_val = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                client = LLMClient()
                with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                    _ = client.client
            finally:
                if old_val:
                    os.environ["ANTHROPIC_API_KEY"] = old_val


class TestCountTokens:
    """Tests for token counting."""

    def test_basic_text(self, client: LLMClient) -> None:
        tokens = client.count_tokens("Hello, world!")
        assert tokens >= 1

    def test_empty_text(self, client: LLMClient) -> None:
        tokens = client.count_tokens("")
        assert tokens == 1  # min of 1

    def test_longer_text(self, client: LLMClient) -> None:
        text = "a" * 400  # ~100 tokens at 4 chars/token
        tokens = client.count_tokens(text)
        assert tokens == 100


class TestEstimateCost:
    """Tests for cost estimation."""

    def test_basic_estimate(self, client: LLMClient) -> None:
        estimate = client.estimate_cost(
            "Hello, how are you?", estimated_output_tokens=500
        )
        assert isinstance(estimate, CostEstimate)
        assert estimate.input_tokens >= 1
        assert estimate.output_tokens == 500
        assert estimate.total_cost_usd > 0

    def test_model_pricing(self, client: LLMClient) -> None:
        est = client.estimate_cost("test", model="claude-sonnet-4-20250514")
        assert est.model == "claude-sonnet-4-20250514"
        assert est.total_cost_usd >= 0

    def test_unknown_model_uses_defaults(self, client: LLMClient) -> None:
        est = client.estimate_cost("test", model="unknown-model-v9")
        assert est.total_cost_usd >= 0


class TestGenerate:
    """Tests for the generate method with mocked API."""

    def _mock_response(
        self,
        text: str = "Generated docs.",
        input_tokens: int = 50,
        output_tokens: int = 100,
    ) -> MagicMock:
        """Create a mock Anthropic API response."""
        response = MagicMock()
        content_block = MagicMock()
        content_block.text = text
        response.content = [content_block]
        response.usage.input_tokens = input_tokens
        response.usage.output_tokens = output_tokens
        response.model = "claude-sonnet-4-20250514"
        response.stop_reason = "end_turn"
        return response

    def test_basic_generation(self, client: LLMClient) -> None:
        mock_resp = self._mock_response()
        with patch.object(client, "_client") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            result = client.generate("Write a docstring for this function.")

        assert result.content == "Generated docs."
        assert result.usage.input_tokens == 50
        assert result.usage.output_tokens == 100

    def test_generation_with_system(self, client: LLMClient) -> None:
        mock_resp = self._mock_response()
        with patch.object(client, "_client") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            result = client.generate(
                "Write docs.",
                system="You are a documentation expert.",
            )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "You are a documentation expert."
        assert result.content == "Generated docs."

    def test_cumulative_usage(self, client: LLMClient) -> None:
        mock_resp = self._mock_response(input_tokens=10, output_tokens=20)
        with patch.object(client, "_client") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            client.generate("First call")
            client.generate("Second call")

        assert client.total_usage.input_tokens == 20
        assert client.total_usage.output_tokens == 40

    def test_custom_max_tokens(self, client: LLMClient) -> None:
        mock_resp = self._mock_response()
        with patch.object(client, "_client") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            client.generate("test", max_tokens=2048)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 2048

    def test_custom_temperature(self, client: LLMClient) -> None:
        mock_resp = self._mock_response()
        with patch.object(client, "_client") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            client.generate("test", temperature=0.8)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 0.8


class TestRetryLogic:
    """Tests for retry behavior on API errors."""

    def test_retry_on_rate_limit(self, client: LLMClient) -> None:
        import anthropic as anth

        mock_resp = MagicMock()
        content_block = MagicMock()
        content_block.text = "Success after retry"
        mock_resp.content = [content_block]
        mock_resp.usage.input_tokens = 10
        mock_resp.usage.output_tokens = 10
        mock_resp.model = "claude-sonnet-4-20250514"
        mock_resp.stop_reason = "end_turn"

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        rate_limit_error = anth.RateLimitError(
            message="Rate limited",
            response=mock_response,
            body={"error": {"message": "Rate limited", "type": "rate_limit_error"}},
        )

        with patch.object(client, "_client") as mock_client:
            mock_client.messages.create.side_effect = [
                rate_limit_error,
                mock_resp,
            ]
            result = client.generate("test")

        assert result.content == "Success after retry"
        assert mock_client.messages.create.call_count == 2

    def test_no_retry_on_client_error(self, client: LLMClient) -> None:
        import anthropic as anth

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}

        bad_request = anth.BadRequestError(
            message="Bad request",
            response=mock_response,
            body={"error": {"message": "Bad request", "type": "invalid_request_error"}},
        )

        with patch.object(client, "_client") as mock_client:
            mock_client.messages.create.side_effect = bad_request
            with pytest.raises(anth.BadRequestError):
                client.generate("test")

        assert mock_client.messages.create.call_count == 1
