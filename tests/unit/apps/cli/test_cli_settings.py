import pytest

from pydantic import ValidationError

from caching_svc.apps.cli.settings import parse_cli_settings


pytestmark = pytest.mark.unit

JSON_INPUT = '{"list_1": ["a"], "list_2": ["b"]}'


def test_parses_short_options():
    settings = parse_cli_settings(
        ["-h", "http://cache:9000", "-r", "3", "-j", JSON_INPUT, "-o", "out.jsonl"]
    )

    assert str(settings.host) == "http://cache:9000/"
    assert settings.repeat == 3
    assert settings.json_payload == JSON_INPUT
    assert settings.output_file == "out.jsonl"


def test_parses_long_options_and_defaults():
    settings = parse_cli_settings(["--input", "-"])

    assert str(settings.host) == "http://localhost:8000/"
    assert settings.repeat == 1
    assert settings.input_file == "-"
    assert settings.output_file == "-"


def test_help_is_long_option_only_because_h_means_host(capsys):
    with pytest.raises(SystemExit) as exc_info:
        parse_cli_settings(["--help"])

    help_text = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "-h, --host" in help_text


def test_ignores_environment_variables(monkeypatch):
    monkeypatch.setenv("HOST", "http://from-env")
    monkeypatch.setenv("REPEAT", "4")

    settings = parse_cli_settings(["-j", JSON_INPUT])

    assert str(settings.host) == "http://localhost:8000/"
    assert settings.repeat == 1


@pytest.mark.parametrize(
    "args",
    [
        ["-j", JSON_INPUT, "-r", "0"],
        ["-j", JSON_INPUT, "-h", "not-a-url"],
        ["-j", JSON_INPUT, "-i", "input.json"],
        [],
    ],
    ids=["repeat-not-positive", "invalid-host", "both-inputs", "no-input"],
)
def test_rejects_invalid_arguments(args):
    with pytest.raises(ValidationError):
        parse_cli_settings(args)
