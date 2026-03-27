"""Hand-written guidance for the text widget type."""

TEXT_GUIDANCE = """### Usage

Text widgets are used as **section headers** to structure the dashboard narrative.

### Example

```json
{
  "id": "header_analysis",
  "position": {"x": 0, "y": 4, "w": 12, "h": 1},
  "widget": {
    "type": "text",
    "config": {"content": "## Trends & Breakdown"}
  }
}
```

### Best Practices

- Use `## Heading` markdown for section titles
- Place before each dashboard section (y=4 before charts, y=15 before tables)
- Default width w=12, h=1
- No dataSource needed — text is static content
- Keep content concise — these are signposts, not paragraphs
"""
