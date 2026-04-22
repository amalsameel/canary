from canary.prompt_firewall import scan_prompt, luhn_valid, shannon_entropy
from canary.risk import compute_risk_score


def test_no_findings_on_safe_prompt():
    findings = scan_prompt("Fix the bug in the login function, please.")
    assert findings == []


def test_openai_key_flagged():
    findings = scan_prompt("my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ fix things")
    kinds = [f.description for f in findings]
    assert "API key" in kinds
    assert all(f.severity == "CRITICAL" for f in findings if f.description == "API key")


def test_github_token_flagged():
    findings = scan_prompt("GH token ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    assert any("GitHub" in f.description for f in findings)


def test_aws_key_flagged():
    findings = scan_prompt("aws key AKIAIOSFODNN7EXAMPLE in the prompt")
    assert any("AWS" in f.description for f in findings)


def test_email_flagged_medium():
    findings = scan_prompt("contact me at john.doe@example.com")
    assert any(f.description == "Email address" and f.severity == "MEDIUM" for f in findings)


def test_ssn_flagged_critical():
    findings = scan_prompt("my ssn is 123-45-6789")
    assert any("SSN" in f.description and f.severity == "CRITICAL" for f in findings)


def test_luhn_valid_credit_card():
    # Visa test number
    assert luhn_valid("4111111111111111")
    # Invalid
    assert not luhn_valid("4111111111111112")


def test_credit_card_requires_luhn():
    good = "my card 4111111111111111 is fine"
    bad  = "random number 1234567890123456 is not a card"
    good_findings = [f for f in scan_prompt(good) if "Credit card" in f.description]
    bad_findings  = [f for f in scan_prompt(bad)  if "Credit card" in f.description]
    assert good_findings
    assert not bad_findings


def test_entropy_ignores_git_sha():
    # Git SHA should NOT be flagged as entropy even though it's high-entropy
    findings = scan_prompt("commit abc1234567890abcdef1234567890abcdef12345678")
    entropy_findings = [f for f in findings if f.kind == "entropy"]
    assert not entropy_findings


def test_entropy_flags_unknown_high_entropy():
    token = "Xk9!vP2mQ@7zLw4bN8cR3sT6aE1u"  # > 20 chars, high entropy, not a known pattern
    findings = scan_prompt(f"here is {token}")
    assert any(f.kind == "entropy" for f in findings)


def test_shannon_entropy_basic():
    assert shannon_entropy("") == 0.0
    assert shannon_entropy("aaaa") == 0.0
    assert shannon_entropy("ab") == 1.0


def test_api_key_scores_high_risk():
    findings = scan_prompt("my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ fix things")
    score = compute_risk_score(findings)
    assert score >= 65


def test_api_key_scores_higher_than_email():
    email_only = compute_risk_score(scan_prompt("contact me at john.doe@example.com"))
    api_only = compute_risk_score(scan_prompt("my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ"))
    assert api_only > email_only


def test_combined_findings_raise_total_risk():
    api_only = compute_risk_score(scan_prompt("my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ"))
    combined = compute_risk_score(
        scan_prompt("my key is sk-abc123xyzDEFGHIJKLMNOPQRSTUVWXYZ and my email john@example.com")
    )
    assert combined > api_only
