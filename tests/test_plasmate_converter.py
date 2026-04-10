"""Tests for markitdown-plasmate plugin."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from markitdown_plasmate import PlasmateConverter, __plugin_interface_version__, register_converters
from markitdown import StreamInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stream_info(url: str = "", mimetype: str = "text/html") -> StreamInfo:
    return StreamInfo(url=url, mimetype=mimetype)


def _completed_process(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=""
    )


# ---------------------------------------------------------------------------
# Package metadata
# ---------------------------------------------------------------------------

class TestPackageMetadata:
    def test_plugin_interface_version(self):
        assert __plugin_interface_version__ == 1

    def test_converter_importable(self):
        assert PlasmateConverter is not None

    def test_register_converters_importable(self):
        assert callable(register_converters)


# ---------------------------------------------------------------------------
# PlasmateConverter.accepts()
# ---------------------------------------------------------------------------

class TestAccepts:
    def setup_method(self):
        self.converter = PlasmateConverter()

    def test_accepts_http_url(self):
        stream = MagicMock()
        assert self.converter.accepts(stream, _stream_info(url="http://example.com"))

    def test_accepts_https_url(self):
        stream = MagicMock()
        assert self.converter.accepts(stream, _stream_info(url="https://example.com"))

    def test_rejects_no_url(self):
        stream = MagicMock()
        assert not self.converter.accepts(stream, _stream_info(url=""))

    def test_rejects_local_file(self):
        stream = MagicMock()
        assert not self.converter.accepts(stream, _stream_info(url="file:///etc/passwd"))

    def test_rejects_none_url(self):
        stream = MagicMock()
        assert not self.converter.accepts(stream, StreamInfo())


# ---------------------------------------------------------------------------
# PlasmateConverter init validation
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_format(self):
        c = PlasmateConverter()
        assert c.output_format == "markdown"

    def test_valid_formats(self):
        for fmt in ("markdown", "text", "som", "links"):
            c = PlasmateConverter(output_format=fmt)
            assert c.output_format == fmt

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="output_format must be one of"):
            PlasmateConverter(output_format="html")

    def test_timeout_stored(self):
        c = PlasmateConverter(timeout=60)
        assert c.timeout == 60

    def test_selector_stored(self):
        c = PlasmateConverter(selector="article")
        assert c.selector == "article"

    def test_constructable_without_binary(self):
        """Init must succeed even when plasmate binary is absent."""
        with patch("shutil.which", return_value=None):
            c = PlasmateConverter()
        assert c is not None


# ---------------------------------------------------------------------------
# PlasmateConverter.convert() — happy path
# ---------------------------------------------------------------------------

class TestConvert:
    def setup_method(self):
        self.converter = PlasmateConverter()
        self.stream = MagicMock()
        self.si = _stream_info(url="https://example.com")

    def test_successful_fetch_returns_markdown(self):
        with patch("shutil.which", return_value="/usr/local/bin/plasmate"), \
             patch("subprocess.run", return_value=_completed_process("# Heading\n\nBody text.")):
            result = self.converter.convert(self.stream, self.si)
        assert "# Heading" in result.markdown
        assert "Body text." in result.markdown

    def test_no_url_returns_error(self):
        result = self.converter.convert(self.stream, StreamInfo())
        assert "Error" in result.markdown
        assert result.title is None

    def test_nonzero_returncode_returns_error(self):
        with patch("shutil.which", return_value="/usr/local/bin/plasmate"), \
             patch("subprocess.run", return_value=_completed_process("", returncode=1)):
            result = self.converter.convert(self.stream, self.si)
        assert "Error" in result.markdown
        assert "exited 1" in result.markdown

    def test_timeout_returns_error(self):
        with patch("shutil.which", return_value="/usr/local/bin/plasmate"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="plasmate", timeout=30)):
            result = self.converter.convert(self.stream, self.si)
        assert "timed out" in result.markdown

    def test_missing_binary_raises_import_error(self):
        """If plasmate is not installed, convert() raises ImportError."""
        with patch("shutil.which", return_value=None), \
             patch.dict("sys.modules", {"plasmate": None}):
            with pytest.raises(ImportError, match="plasmate is required"):
                self.converter.convert(self.stream, self.si)

    def test_empty_output_returns_warning(self):
        with patch("shutil.which", return_value="/usr/local/bin/plasmate"), \
             patch("subprocess.run", return_value=_completed_process("")):
            result = self.converter.convert(self.stream, self.si)
        assert "Warning" in result.markdown or "empty" in result.markdown.lower()


# ---------------------------------------------------------------------------
# Command construction
# ---------------------------------------------------------------------------

class TestCommandConstruction:
    def test_basic_cmd_includes_url_and_format(self):
        c = PlasmateConverter()
        with patch("shutil.which", return_value="/usr/bin/plasmate"), \
             patch("subprocess.run", return_value=_completed_process("content")) as mock_run:
            c.convert(MagicMock(), _stream_info(url="https://example.com"))
        cmd = mock_run.call_args[0][0]
        assert "/usr/bin/plasmate" in cmd
        assert "fetch" in cmd
        assert "https://example.com" in cmd
        assert "--format" in cmd
        assert "markdown" in cmd

    def test_timeout_converted_to_ms(self):
        c = PlasmateConverter(timeout=45)
        with patch("shutil.which", return_value="/usr/bin/plasmate"), \
             patch("subprocess.run", return_value=_completed_process("ok")) as mock_run:
            c.convert(MagicMock(), _stream_info(url="https://example.com"))
        cmd = mock_run.call_args[0][0]
        assert "45000" in cmd

    def test_selector_added_when_set(self):
        c = PlasmateConverter(selector="main")
        with patch("shutil.which", return_value="/usr/bin/plasmate"), \
             patch("subprocess.run", return_value=_completed_process("ok")) as mock_run:
            c.convert(MagicMock(), _stream_info(url="https://example.com"))
        cmd = mock_run.call_args[0][0]
        assert "--selector" in cmd
        assert "main" in cmd

    def test_selector_omitted_when_none(self):
        c = PlasmateConverter(selector=None)
        with patch("shutil.which", return_value="/usr/bin/plasmate"), \
             patch("subprocess.run", return_value=_completed_process("ok")) as mock_run:
            c.convert(MagicMock(), _stream_info(url="https://example.com"))
        cmd = mock_run.call_args[0][0]
        assert "--selector" not in cmd

    def test_som_format_passed_through(self):
        c = PlasmateConverter(output_format="som")
        with patch("shutil.which", return_value="/usr/bin/plasmate"), \
             patch("subprocess.run", return_value=_completed_process("{}")) as mock_run:
            c.convert(MagicMock(), _stream_info(url="https://example.com"))
        cmd = mock_run.call_args[0][0]
        assert "som" in cmd


# ---------------------------------------------------------------------------
# register_converters
# ---------------------------------------------------------------------------

class TestRegisterConverters:
    def test_registers_plasmate_converter(self):
        mock_md = MagicMock()
        register_converters(mock_md)
        mock_md.register_converter.assert_called_once()
        registered = mock_md.register_converter.call_args[0][0]
        assert isinstance(registered, PlasmateConverter)

    def test_custom_format_passed_through(self):
        mock_md = MagicMock()
        register_converters(mock_md, plasmate_format="text")
        registered = mock_md.register_converter.call_args[0][0]
        assert registered.output_format == "text"

    def test_custom_timeout_passed_through(self):
        mock_md = MagicMock()
        register_converters(mock_md, plasmate_timeout=60)
        registered = mock_md.register_converter.call_args[0][0]
        assert registered.timeout == 60
