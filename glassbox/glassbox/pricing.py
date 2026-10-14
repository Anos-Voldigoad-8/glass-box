"""Dynamic model pricing for GLASS BOX SDK."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import yaml

from .types import TokenUsage

# Global pricing cache
_pricing_cache: dict[str, dict[str, float]] = {}
_pricing_lock = threading.Lock()
_pricing_loaded = False


def _get_pricing_file_path() -> Path:
    """Get the path to the pricing YAML file."""
    # Check for custom pricing file via environment variable
    custom_path = os.environ.get("GLASSBOX_PRICING_FILE")
    if custom_path:
        return Path(custom_path)
    
    # Default to the packaged pricing.yaml
    return Path(__file__).parent / "pricing.yaml"


def load_pricing(force_reload: bool = False) -> dict[str, dict[str, float]]:
    """Load pricing from YAML file."""
    global _pricing_cache, _pricing_loaded
    
    with _pricing_lock:
        if _pricing_loaded and not force_reload:
            return _pricing_cache
        
        pricing_path = _get_pricing_file_path()
        
        if not pricing_path.exists():
            # Return empty dict, will use fallback pricing
            _pricing_cache = {}
            _pricing_loaded = True
            return _pricing_cache
        
        try:
            with open(pricing_path, "r") as f:
                data = yaml.safe_load(f) or {}
            
            # Flatten the nested structure: provider -> model -> {input, output}
            flat_pricing = {}
            for provider, models in data.items():
                if isinstance(models, dict):
                    for model, rates in models.items():
                        if isinstance(rates, dict) and "input" in rates and "output" in rates:
                            key = f"{provider}:{model}"
                            flat_pricing[key] = {
                                "input": float(rates["input"]),
                                "output": float(rates["output"]),
                            }
            
            _pricing_cache = flat_pricing
            _pricing_loaded = True
            return _pricing_cache
            
        except Exception as e:
            # Log error but don't crash - fall back to empty pricing
            import logging
            logging.getLogger(__name__).warning(f"Failed to load pricing: {e}")
            _pricing_cache = {}
            _pricing_loaded = True
            return _pricing_cache


def get_model_pricing(provider: str, model: str) -> dict[str, float] | None:
    """Get pricing for a specific model from a provider."""
    # Normalize provider name
    normalized_provider = normalize_provider(provider)
    pricing = load_pricing()
    
    # Try exact match first
    key = f"{normalized_provider}:{model}"
    if key in pricing:
        return pricing[key]
    
    # Try case-insensitive match
    key_lower = key.lower()
    for k, v in pricing.items():
        if k.lower() == key_lower:
            return v
    
    # Try provider wildcard (e.g., ollama:*)
    wildcard_key = f"{normalized_provider}:*"
    if wildcard_key in pricing:
        return pricing[wildcard_key]
    
    # Try model name variations (remove version suffixes, etc.)
    model_variants = [
        model,
        model.lower(),
        model.replace(".", "").replace("-", ""),
        model.split("-")[0] if "-" in model else model,
    ]
    
    for variant in model_variants:
        variant_key = f"{normalized_provider}:{variant}"
        if variant_key in pricing:
            return pricing[variant_key]
    
    return None


def calculate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost for a model call using dynamic pricing."""
    pricing = get_model_pricing(provider, model)
    
    if pricing is None:
        # Fallback to hardcoded defaults
        from .types import calculate_cost as legacy_calculate_cost
        return legacy_calculate_cost(model, prompt_tokens, completion_tokens)
    
    input_cost = (prompt_tokens * pricing["input"]) / 1_000_000
    output_cost = (completion_tokens * pricing["output"]) / 1_000_000
    return input_cost + output_cost


def update_token_usage_cost(usage: TokenUsage, provider: str, model: str) -> None:
    """Update TokenUsage with calculated cost based on dynamic pricing."""
    usage.cost_usd = calculate_cost(provider, model, usage.prompt_tokens, usage.completion_tokens)


def get_all_pricing() -> dict[str, dict[str, float]]:
    """Get all loaded pricing data."""
    return load_pricing().copy()


def reload_pricing() -> dict[str, dict[str, float]]:
    """Force reload pricing from file."""
    return load_pricing(force_reload=True)


# Provider name normalization
PROVIDER_ALIASES = {
    "openai": "openai",
    "azure": "openai",
    "anthropic": "anthropic",
    "google": "google",
    "vertex": "google",
    "mistral": "mistral",
    "cohere": "cohere",
    "perplexity": "perplexity",
    "ollama": "ollama",
    "local": "ollama",
}


def normalize_provider(provider: str) -> str:
    """Normalize provider name to standard form."""
    return PROVIDER_ALIASES.get(provider.lower(), provider.lower())


def calculate_cost_normalized(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost with provider normalization."""
    normalized = normalize_provider(provider)
    return calculate_cost(normalized, model, prompt_tokens, completion_tokens)


__all__ = [
    "calculate_cost",
    "calculate_cost_normalized",
    "get_all_pricing",
    "get_model_pricing",
    "load_pricing",
    "normalize_provider",
    "reload_pricing",
    "update_token_usage_cost",
]