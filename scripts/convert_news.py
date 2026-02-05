#!/usr/bin/env python3
"""Convert daily news to markdown for RAG testing."""

import sys
from pathlib import Path
from datetime import datetime

def convert_news_to_markdown(news_file: Path, output_file: Path):
    """Convert the daily news file to proper markdown format."""

    content = news_file.read_text()

    # Create structured markdown
    md_content = f"""# {content.split(chr(10))[0].replace('# ', '')}

Generated: {datetime.now().isoformat()}

---

{content}

---

*This document was auto-generated from daily tech news for RAG testing.*
"""

    output_file.write_text(md_content)
    print(f"✅ Converted {news_file} to {output_file}")
    return output_file

if __name__ == "__main__":
    news_file = Path("/Users/edmund/.openclaw/workspace/memory/2026-02-06.md")
    output_file = Path("/Users/edmund/work/llm-md-cli/test_data/news-2026-02-06.md")

    output_file.parent.mkdir(exist_ok=True)
    convert_news_to_markdown(news_file, output_file)
