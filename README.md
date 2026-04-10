# markitdown-plasmate

A [MarkItDown](https://github.com/microsoft/markitdown) plugin that converts live URLs via [Plasmate](https://github.com/plasmate-labs/plasmate) instead of BeautifulSoup — returning 10-100x fewer tokens with no API key required.

## Why?

MarkItDown's built-in HTML converter fetches a URL, strips `<script>` tags, and converts whatever remains with BeautifulSoup. For a typical news article that means ~60,000 tokens of navigation menus, cookie banners, sidebar widgets, and footer links wrapped around ~2,000 tokens of actual content.

Plasmate is an open-source Rust browser engine that renders the page properly and returns only the meaningful content as clean Markdown. The token difference is significant:

| Site | Raw HTML (BeautifulSoup) | Plasmate | Reduction |
|------|--------------------------|----------|-----------|
| TechCrunch article | ~75,000 tokens | ~975 tokens | 77× |
| Average (45 sites) | ~45,000 tokens | ~2,500 tokens | 17.7× |

The plugin slots in specifically for `http://` and `https://` URL inputs — local files (PDF, Word, Excel, etc.) continue to use MarkItDown's native converters unchanged.

## Installation

```bash
pip install markitdown-plasmate
pip install plasmate          # the Rust browser engine
```

Or with cargo:

```bash
cargo install plasmate
```

## Usage

### CLI

```bash
markitdown --use-plugins https://techcrunch.com/2025/04/08/some-article/
```

### Python

```python
from markitdown import MarkItDown

md = MarkItDown(enable_plugins=True)
result = md.convert("https://blog.cloudflare.com/ai-crawler-traffic-by-purpose-and-industry/")
print(result.markdown)
# → clean article content, ~2,000 tokens instead of ~60,000
```

### Options

Pass plugin options via MarkItDown kwargs:

```python
md = MarkItDown(
    enable_plugins=True,
    plasmate_format="markdown",   # markdown | text | som | links
    plasmate_timeout=30,          # seconds
    plasmate_selector="article",  # CSS selector to scope extraction
)
```

Or use `PlasmateConverter` directly:

```python
from markitdown_plasmate import PlasmateConverter
from markitdown import MarkItDown

md = MarkItDown()
md.register_converter(PlasmateConverter(output_format="markdown", selector="main"))
result = md.convert("https://example.com")
```

## Output formats

| Format | Description |
|--------|-------------|
| `markdown` | Clean Markdown (default) |
| `text` | Plain text, no markup |
| `som` | Structured Object Model — semantic JSON tree |
| `links` | Extracted hyperlinks only |

## When it applies

The plugin **only intercepts `http://` and `https://` URLs**. All other MarkItDown input types (PDF, Word, Excel, images, audio, local HTML files) are unaffected.

## Requirements

- Python 3.10+
- `markitdown >= 0.1.0`
- `plasmate` binary on PATH (`pip install plasmate` or `cargo install plasmate`)

The plugin is constructable without the binary — `ImportError` is raised on the first conversion attempt with clear install instructions.

## Related

- [Plasmate](https://github.com/plasmate-labs/plasmate) — the open-source Rust browser engine
- [somspec.org](https://somspec.org) — Structured Object Model specification
- [MarkItDown](https://github.com/microsoft/markitdown) — the Python file-to-Markdown converter this plugin extends
