"""JellyClaw: a local hierarchy of AI agents running on Ollama."""

from jellyclaw.capabilities import Capability, CapabilityError, learn, teach

__version__ = "0.1.0"

__all__ = ["Capability", "CapabilityError", "learn", "teach", "__version__"]
