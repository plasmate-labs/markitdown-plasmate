"""
markitdown-plasmate
===================
A MarkItDown plugin that replaces the default BeautifulSoup HTML converter
for live URLs with Plasmate -- an open-source Rust browser engine.

When MarkItDown processes an http/https URL, this converter intercepts it,
calls ``plasmate fetch <url> --format markdown`` as a subprocess, and returns
the pre-processed, token-efficient Markdown instead of raw BeautifulSoup output.

Typical results (measured across 45 real sites):
  - Average compression: 17.7x over raw HTML
  - Peak compression: 77x (TechCrunch)

Install Plasmate: pip install plasmate
Docs: https://github.com/plasmate-labs/plasmate
"""

import shutil
import subprocess
from typing import Any, BinaryIO, Literal, Optional

from markitdown import (
    DocumentConverter,
    DocumentConverterResult,
    MarkItDown,
    StreamInfo,
)

__plugin_interface_version__ = 1

_VALID_FORMATS = ("markdown", "text", "som", "links")

_INSTALL_MSG = (
    "plasmate is required for the markitdown-plasmate plugin. "
    "Install it with: pip install plasmate\n"
    "Docs: https://github.com/plasmate-labs/plasmate"
)


def _find_plasmate() -> Optional[str]:
    """Locate the plasmate binary on PATH or via the plasmate Python package."""
    path = shutil.which("plasmate")
    if path:
        return path
    try:
        import plasmate as _p  # noqa: F401

        return shutil.which("plasmate")
    except ImportError:
        return None


def register_converters(markitdown: MarkItDown, **kwargs: Any) -> None:
    """
    Called during MarkItDown construction to register this plugin's converters.

    PlasmateConverter is registered first so it takes priority over the built-in
    HtmlConverter for http/https URLs.
    """
    output_format: Literal["markdown", "text", "som", "links"] = kwargs.get(
        "plasmate_format", "markdown"
    )
    timeout: int = int(kwargs.get("plasmate_timeout", 30))
    selector: Optional[str] = kwargs.get("plasmate_selector", None)

    markitdown.register_converter(
        PlasmateConverter(
            output_format=output_format,
            timeout=timeout,
            selector=selector,
        )
    )


class PlasmateConverter(DocumentConverter):
    """
    MarkItDown converter for live http/https URLs using Plasmate.

    Replaces the default BeautifulSoup HTML converter for URL inputs, returning
    pre-processed Markdown (or text/SOM/links) with 10-100x fewer tokens than
    raw HTML.

    Parameters
    ----------
    output_format : str
        Content format returned to the caller. One of ``"markdown"`` (default),
        ``"text"``, ``"som"`` (Structured Object Model JSON), or ``"links"``
        (extracted hyperlinks only).
    timeout : int
        Per-request timeout in seconds. Defaults to 30.
    selector : str, optional
        CSS selector or ARIA role to scope extraction to a specific page region
        (e.g. ``"main"`` or ``"article"``).
    """

    def __init__(
        self,
        output_format: Literal["markdown", "text", "som", "links"] = "markdown",
        timeout: int = 30,
        selector: Optional[str] = None,
    ) -> None:
        if output_format not in _VALID_FORMATS:
            raise ValueError(
                f"output_format must be one of {_VALID_FORMATS}; "
                f"got {output_format!r}"
            )
        self.output_format = output_format
        self.timeout = timeout
        self.selector = selector

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        """Accept http/https URLs only -- leave local files to other converters."""
        url = stream_info.url or ""
        return url.startswith("http://") or url.startswith("https://")

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> DocumentConverterResult:
        """
        Fetch and convert a URL via Plasmate.

        The ``file_stream`` (pre-fetched raw HTML from MarkItDown's requests
        session) is intentionally ignored; Plasmate fetches the URL directly
        so it can render JavaScript and apply SOM extraction.
        """
        url = stream_info.url
        if not url:
            return DocumentConverterResult(
                title=None,
                markdown="Error: PlasmateConverter called without a URL in stream_info.",
            )

        plasmate_bin = _find_plasmate()
        if plasmate_bin is None:
            raise ImportError(_INSTALL_MSG)

        cmd = [
            plasmate_bin,
            "fetch",
            url,
            "--format",
            self.output_format,
            "--timeout",
            str(self.timeout * 1000),  # plasmate accepts milliseconds
        ]
        if self.selector:
            cmd += ["--selector", self.selector]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 5,
            )
        except subprocess.TimeoutExpired:
            return DocumentConverterResult(
                title=None,
                markdown=f"Error: plasmate timed out fetching {url} after {self.timeout}s.",
            )

        if result.returncode != 0:
            return DocumentConverterResult(
                title=None,
                markdown=(
                    f"Error: plasmate exited {result.returncode} for {url}.\n\n"
                    f"{result.stderr[:300]}"
                ),
            )

        content = result.stdout.strip()
        if not content:
            return DocumentConverterResult(
                title=None,
                markdown=f"Warning: plasmate returned empty content for {url}.",
            )

        return DocumentConverterResult(
            title=None,
            markdown=content,
        )
