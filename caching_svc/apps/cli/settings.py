import argparse

from collections.abc import Sequence
from typing import Self, override

from pydantic import AliasChoices, Field, HttpUrl, PositiveInt, model_validator
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


STD_STREAM = "-"


class CliSettings(BaseSettings):
    """Send payloads to the caching service and write the generated outputs."""

    host: HttpUrl = Field(
        default=HttpUrl("http://localhost:8000"),
        validation_alias=AliasChoices("h", "host"),
        description="URL of the caching service",
    )
    repeat: PositiveInt = Field(
        default=1,
        validation_alias=AliasChoices("r", "repeat"),
        description="number of times the payload is created and read back",
    )
    input_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("i", "input"),
        description=f"JSON input file, '{STD_STREAM}' for stdin",
    )
    json_payload: str | None = Field(
        default=None,
        validation_alias=AliasChoices("j", "json"),
        description="JSON input passed inline",
    )
    output_file: str = Field(
        default=STD_STREAM,
        validation_alias=AliasChoices("o", "output"),
        description=f"output file, '{STD_STREAM}' for stdout",
    )

    model_config = SettingsConfigDict(cli_hide_none_type=True)

    @classmethod
    @override
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Command line only: aliases bypass ``env_prefix``, so env/.env sources would let generic
        # variables such as HOST or INPUT silently override the arguments.
        return (init_settings,)

    @model_validator(mode="after")
    def check_single_input_source(self) -> Self:
        if (self.input_file is None) == (self.json_payload is None):
            raise ValueError("exactly one of --input or --json must be provided")
        return self


def parse_cli_settings(args: Sequence[str]) -> CliSettings:
    """Parse command line arguments into validated settings.

    The spec assigns ``-h`` to ``--host``, so the parser is built without argparse's default
    ``-h/--help`` and help stays available as ``--help`` only.
    """
    parser = argparse.ArgumentParser(
        prog="cache-cli",
        description=CliSettings.__doc__,
        add_help=False,
        allow_abbrev=False,
    )
    parser.add_argument("--help", action="help", help="show this help message and exit")
    source = CliSettingsSource(CliSettings, root_parser=parser)
    return CliSettings(_cli_settings_source=source(args=list(args)))
