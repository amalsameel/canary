from canary.drift import cosine_similarity


def test_identical_vectors():
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == 1.0


def test_orthogonal_vectors():
    assert cosine_similarity([1, 0], [0, 1]) == 0.0


def test_zero_vector_handled():
    assert cosine_similarity([0, 0, 0], [1, 2, 3]) == 1.0


def test_empty_vector_handled():
    assert cosine_similarity([], [1, 2, 3]) == 1.0
