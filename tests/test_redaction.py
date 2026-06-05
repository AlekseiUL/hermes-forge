from hermes_forge.redaction import redact_text, safe_path_label


def test_redacts_token_shapes_and_sensitive_absolute_paths():
    raw_path = "/" + "Users" + "/alex/private"
    temp_path = "/" + "private" + "/var/folders/example/experiment"
    sample_key = "sk-" + "a" * 20
    text = sample_key + " " + raw_path + " " + temp_path
    out = redact_text(text)
    assert sample_key not in out
    assert raw_path not in out
    assert temp_path not in out
    assert "[REDACTED]" in out
    assert "[REDACTED_PATH]" in out


def test_safe_path_label():
    assert "<hermes-home>" in safe_path_label("/tmp/hermes/profiles/a", "/tmp/hermes")


def test_safe_path_label_redacts_temp_paths_without_hermes_home():
    temp_path = "/" + "private" + "/var/folders/example/experiment"
    out = safe_path_label(temp_path)
    assert temp_path not in out
    assert out == "[REDACTED_PATH]"
