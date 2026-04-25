from engine.confidence import ConfidenceLabel, calculate_confidence, confidence_label
from engine.preset_schemas import ValidationConfig
from engine.validator import validate


def test_validate_all_tokens_preserved():
    config = ValidationConfig(
        critical_tokens=[{"name": "code", "regex": r"DOC\.\d{3}"}],
        required_sections=["objetivo"],
    )
    source = "O documento DOC.001 descreve X."
    content = {"objetivo": "Descrever algo sobre DOC.001"}
    r = validate(source, content, config)
    assert r.ok is True
    assert r.critical_tokens_total == 1
    assert r.critical_tokens_found == 1


def test_validate_detects_missing_token():
    config = ValidationConfig(critical_tokens=[{"name": "code", "regex": r"DOC\.\d{3}"}])
    source = "DOC.001 e DOC.002."
    content = {"objetivo": "Algo sobre DOC.001 apenas."}
    r = validate(source, content, config)
    assert r.ok is False
    assert "DOC.002" in r.critical_tokens_missing


def test_validate_detects_missing_section():
    config = ValidationConfig(required_sections=["objetivo", "procedimento"])
    content = {"objetivo": "ok"}
    r = validate("fonte", content, config)
    assert "procedimento" in r.sections_missing


def test_validate_invalid_regex_is_skipped():
    config = ValidationConfig(critical_tokens=[{"name": "bad", "regex": "([invalid"}])
    r = validate("anything", {"x": "y"}, config)
    assert r.critical_tokens_total == 0


def test_confidence_high_when_all_ok():
    config = ValidationConfig(
        critical_tokens=[{"name": "c", "regex": r"\d+"}],
        required_sections=["a"],
    )
    r = validate("123", {"a": "x contendo 123"}, config)
    score = calculate_confidence(r)
    assert score >= 0.9
    assert confidence_label(score) == ConfidenceLabel.HIGH


def test_confidence_low_when_missing_tokens():
    config = ValidationConfig(
        critical_tokens=[{"name": "c", "regex": r"\d+"}],
        required_sections=["a"],
    )
    r = validate("1 2 3 4 5", {"a": "só 1"}, config)
    score = calculate_confidence(r)
    assert score < 0.9


def test_confidence_labels():
    from engine.validator import ValidationResult

    r_high = ValidationResult(True, 10, 10, 5, 5, [], [])
    r_mid = ValidationResult(False, 10, 7, 5, 4, [], [])
    r_low = ValidationResult(False, 10, 2, 5, 1, [], [])

    assert confidence_label(calculate_confidence(r_high)) == ConfidenceLabel.HIGH
    assert confidence_label(calculate_confidence(r_mid)) in (ConfidenceLabel.HIGH, ConfidenceLabel.MEDIUM)
    assert confidence_label(calculate_confidence(r_low)) == ConfidenceLabel.LOW


def test_confidence_empty_config_is_perfect():
    config = ValidationConfig()
    r = validate("text", {}, config)
    score = calculate_confidence(r)
    assert score == 1.0
