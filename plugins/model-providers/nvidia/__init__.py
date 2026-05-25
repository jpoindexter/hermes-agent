"""NVIDIA NIM provider profile."""

from providers import register_provider
from providers.base import ProviderProfile

nvidia = ProviderProfile(
    name="nvidia",
    aliases=("nvidia-nim",),
    env_vars=("NVIDIA_API_KEY",),
    display_name="NVIDIA NIM",
    description="NVIDIA NIM — accelerated inference",
    signup_url="https://build.nvidia.com/",
    fallback_models=(
        # Verified against Jason's NVIDIA account on 2026-05-20.
        "meta/llama-3.3-70b-instruct",
        "nvidia/llama-3.3-nemotron-super-49b-v1",
        "qwen/qwen3-next-80b-a3b-instruct",
        "mistralai/mistral-small-4-119b-2603",
        "meta/llama-4-maverick-17b-128e-instruct",
    ),
    base_url="https://integrate.api.nvidia.com/v1",
    default_max_tokens=16384,
)

register_provider(nvidia)
