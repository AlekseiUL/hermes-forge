from hermes_forge.redaction import redact_text, safe_path_label


def test_redacts_token_shapes_and_user_paths():
    raw_path = "/" + "Users" + "/alex/private"
    sample_key = "sk-" + "a" * 20
    text = sample_key + " " + raw_path
    out = redact_text(text)
    assert sample_key not in out
    assert raw_path not in out
    assert "[REDACTED]" in out


def test_safe_path_label():
    assert "<hermes-home>" in safe_path_label("/tmp/hermes/profiles/a", "/tmp/hermes")
