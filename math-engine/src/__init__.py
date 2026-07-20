"""
Math Engine — symbolic, numeric, financial, probability, and plotting.
LLM NEVER computes — this engine does the actual math.
"""

from .engine import MathEngine, ProblemType, SolveResult

__version__ = "0.1.0"
__all__ = ["MathEngine", "ProblemType", "SolveResult"]
