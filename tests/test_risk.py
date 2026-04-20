from canary.risk import RISK_ASSESSMENT_THRESHOLD, risk_assessment, risk_level


def test_risk_assessment_hidden_below_threshold():
    assert risk_assessment(RISK_ASSESSMENT_THRESHOLD - 1) is None


def test_risk_assessment_appears_at_threshold():
    assessment = risk_assessment(RISK_ASSESSMENT_THRESHOLD)
    assert assessment is not None
    assert assessment[0] == "manual review advised"


def test_risk_assessment_escalates_for_high_scores():
    assessment = risk_assessment(84)
    assert assessment is not None
    assert assessment[0] == "hard stop recommended"
    assert risk_level(84)[0] == "high"
