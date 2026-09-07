"""The final answer must never carry a fenced SQL block.

Prod, 2026-09-07: under the privacy floor the orchestrator had no row values,
so it pasted the query in a ```sql fence and told the user to run it in their
own console. The prompt rule that forbids this had never reached the live
(DB-seeded) prompt, and nothing on the output path removed it. This is the
deterministic half of the fix — it holds regardless of what the LLM writes.
"""

from backend.agents.orchestrator.graph import (
    _SCRUBBED_EMPTY_MESSAGE,
    _finalize_answer_text,
    _strip_sql_fences,
)


class TestFencedSqlIsRemoved:
    def test_tagged_fence_goes_and_the_prose_stays(self):
        text = (
            "Sunday is the slowest day.\n\n"
            "```sql\nSELECT day, AVG(total) FROM sales GROUP BY day;\n```\n\n"
            "The table below has every weekday."
        )
        out = _strip_sql_fences(text)
        assert "SELECT" not in out
        assert "```" not in out
        assert out.startswith("Sunday is the slowest day.")
        assert out.endswith("The table below has every weekday.")
        assert "\n\n\n" not in out

    def test_the_language_tag_is_case_insensitive(self):
        assert "SELECT" not in _strip_sql_fences("a\n\n```SQL\nSELECT 1;\n```\n")

    def test_an_untagged_fence_that_opens_with_select_goes(self):
        assert "SELECT" not in _strip_sql_fences("a\n\n```\nSELECT 1;\n```\n")

    def test_an_untagged_fence_that_opens_with_a_cte_goes(self):
        out = _strip_sql_fences("a\n\n```\nwith daily as (select 1)\nselect * from daily;\n```\n")
        assert "daily" not in out

    def test_both_fences_in_one_reply_go(self):
        out = _strip_sql_fences("```sql\nSELECT 1;\n```\nmiddle\n```\nSELECT 2;\n```")
        assert "SELECT" not in out
        assert "middle" in out


class TestOtherFencesSurvive:
    """Only SQL is suppressed — a widget spec or a snippet the user asked for
    is a different conversation, and over-stripping would eat real answers."""

    def test_a_json_fence_stays(self):
        text = 'here\n\n```json\n{"a": 1}\n```'
        assert _strip_sql_fences(text) == text

    def test_a_python_fence_stays(self):
        text = "here\n\n```python\nprint(1)\n```"
        assert _strip_sql_fences(text) == text

    def test_an_untagged_prose_fence_stays(self):
        text = "here\n\n```\njust some text\n```"
        assert _strip_sql_fences(text) == text

    def test_inline_backticks_are_left_alone(self):
        """# ponytail: fences only. Inline mentions are the prompt's job."""
        text = "I ran a `SELECT` grouped by weekday."
        assert _strip_sql_fences(text) == text


class TestPassthrough:
    def test_text_without_a_fence_is_returned_unchanged(self):
        text = "Sunday is the slowest day, at $412 average."
        assert _strip_sql_fences(text) is text

    def test_empty_is_returned_unchanged(self):
        assert _strip_sql_fences("") == ""


class TestTheAnswerIsNeverEmptied:
    """The scrubbers are subtractive. An answer that was *only* a SQL fence (or
    only a traceback) sanitizes to "" — and empty is worse than wrong: it skips
    the judge gate and the `token` frame, then persists as an empty assistant
    message that replays as AIMessage(content="") on the next turn.
    """

    def test_a_sql_only_answer_becomes_the_fallback(self):
        out = _finalize_answer_text("```sql\nSELECT day, AVG(total) FROM sales GROUP BY day;\n```")
        assert out == _SCRUBBED_EMPTY_MESSAGE
        assert "SELECT" not in out

    def test_a_traceback_only_answer_becomes_the_fallback(self):
        text = (
            "Traceback (most recent call last):\n"
            '  File "/app/backend/x.py", line 1, in <module>\n'
            "ValueError: boom"
        )
        assert _finalize_answer_text(text) == _SCRUBBED_EMPTY_MESSAGE

    def test_a_bare_exception_line_becomes_the_fallback(self):
        assert _finalize_answer_text("ValueError: bad thing") == _SCRUBBED_EMPTY_MESSAGE

    def test_ordinary_prose_is_untouched(self):
        text = "Sunday is the slowest day, at $412 average."
        assert _finalize_answer_text(text) == text

    def test_prose_plus_a_fence_keeps_the_prose(self):
        out = _finalize_answer_text(
            "Sunday is the slowest day.\n\n```sql\nSELECT 1;\n```"
        )
        assert out == "Sunday is the slowest day."
        assert out != _SCRUBBED_EMPTY_MESSAGE

    def test_empty_input_stays_empty(self):
        """No fallback for a turn that genuinely produced nothing — that is the
        tool-only case, and `done` already handles it."""
        assert _finalize_answer_text("") == ""

    def test_every_scrub_still_runs_on_what_survives(self):
        out = _finalize_answer_text(
            "I queried connection 5 for you.\n\n```sql\nSELECT 1;\n```"
        )
        assert "connection 5" not in out
        assert "the database" in out
        assert "SELECT" not in out
