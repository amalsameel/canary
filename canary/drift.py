"""Cosine similarity for drift calculation."""
import math


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Return cosine similarity in [-1, 1]. Returns 1.0 for zero-magnitude inputs."""
    if not v1 or not v2:
        return 1.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 1.0
    return dot / (mag1 * mag2)
