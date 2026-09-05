"""Guard against drift between the two orchestrator prompt paths.

`prompts.py:_ORCHESTRATOR_CHASSIS` and `profile_defaults.py:_ORCHESTRATOR_IDENTITY`
render the same agent and had already drifted: the chassis carried the
`### ask_user_question Rules`, the identity never did. Since
`orchestrator_lean_tools` defaults to False and profiles exist, the DB-seeded
identity is the path that actually runs — so the live prompt had never contained
the ask rules at all.

Both must now compose from backend.agents.orchestrator_prompt_blocks. Modelled on
test_dashboard_prompt_sync.py, which guards the same class of bug for the
dashboard agent.
"""

from backend.agents.orchestrator_prompt_blocks import (
    ORCHESTRATOR_APPROACH,
    ORCHESTRATOR_ASK_RULES,
    ORCHESTRATOR_DASHBOARD_SCOPING,
    ORCHESTRATOR_WORKFLOW,
)
from backend.agents.orchestrator.prompts import _ORCHESTRATOR_CHASSIS
from backend.agents.profile_defaults import DEFAULTS, _ORCHESTRATOR_IDENTITY

_STALE_MARKERS = [
    # The unqualified skip-clause: "1-2 tool calls" with no dashboard carve-out.
    # "build me a sales dashboard" is unambiguous and exactly one tool call, so
    # this wording let the agent skip planning on the very request that needs it.
    'skip directly to execution (e.g., "list my dashboards", "what tables do I have?").\n',
    "skip directly to execution.\n",
    # The blanket ban that read as "never ask the user anything".
    "You MUST handle the full workflow automatically.",
]


class TestBothPathsComposeFromTheSharedBlock:
    def test_chassis_composes_from_the_shared_block(self):
        assert ORCHESTRATOR_WORKFLOW in _ORCHESTRATOR_CHASSIS

    def test_identity_composes_from_the_shared_block(self):
        assert ORCHESTRATOR_WORKFLOW in _ORCHESTRATOR_IDENTITY

    def test_seeded_orchestrator_identity_is_the_constant(self):
        assert DEFAULTS["orchestrator"]["identity"] == _ORCHESTRATOR_IDENTITY

    def test_each_sub_block_reaches_both_consumers(self):
        for block in (ORCHESTRATOR_APPROACH, ORCHESTRATOR_DASHBOARD_SCOPING, ORCHESTRATOR_ASK_RULES):
            assert block in _ORCHESTRATOR_CHASSIS
            assert block in _ORCHESTRATOR_IDENTITY

    def test_the_scoping_block_is_an_exact_removable_substring(self):
        """The kill switch strips it by exact match at render time."""
        assert _ORCHESTRATOR_IDENTITY.count(ORCHESTRATOR_DASHBOARD_SCOPING) == 1
        stripped = _ORCHESTRATOR_IDENTITY.replace(ORCHESTRATOR_DASHBOARD_SCOPING, "")
        assert ORCHESTRATOR_DASHBOARD_SCOPING not in stripped
        assert ORCHESTRATOR_ASK_RULES in stripped, "stripping scoping must not take the ask rules with it"


class TestTheIdentityGainedTheAskRules:
    """The regression this plan exists to fix: the live prompt never had them."""

    def test_identity_now_contains_the_ask_rules(self):
        assert ORCHESTRATOR_ASK_RULES in _ORCHESTRATOR_IDENTITY

    def test_rendered_profile_contains_the_ask_rules(self):
        from backend.agents.profile_renderer import ProfileRenderer, RuntimeContext
        from backend.models.agent_profile import AgentProfile

        profile = AgentProfile(
            agent_type="orchestrator",
            identity=DEFAULTS["orchestrator"]["identity"],
            is_active=True,
            version=1,
        )
        rendered = ProfileRenderer.render(
            profile, RuntimeContext(available_connections=[], connection_metadata=[])
        )
        assert "ask_user_question Rules" in rendered
        assert "One clarification round per request" in rendered

    def test_the_one_round_rule_is_stated(self):
        assert "One clarification round per request" in ORCHESTRATOR_ASK_RULES


class TestSkipPlanningNoLongerClaimsDashboards:
    def test_the_skip_clause_excludes_dashboard_creation(self):
        assert "This never applies to dashboard creation." in ORCHESTRATOR_APPROACH

    def test_tool_call_count_is_explicitly_not_the_test(self):
        assert "the number of tool calls is not the test" in ORCHESTRATOR_APPROACH

    def test_dashboard_creation_always_plans(self):
        assert "Dashboard creation always plans" in ORCHESTRATOR_APPROACH

    def test_no_stale_markers_in_either_consumer(self):
        for marker in _STALE_MARKERS:
            assert marker not in _ORCHESTRATOR_CHASSIS
            assert marker not in _ORCHESTRATOR_IDENTITY


class TestTheFourDimensions:
    def test_all_four_dimensions_are_named(self):
        for dimension in ("Audience & purpose", "Grain", "Time range", "Priority metrics"):
            assert dimension in ORCHESTRATOR_DASHBOARD_SCOPING

    def test_four_dimensions_fits_the_tools_four_question_cap(self):
        """More than four would not fit ask_user_question's validated 1-4 range."""
        numbered = [
            line for line in ORCHESTRATOR_DASHBOARD_SCOPING.splitlines()
            if line[:2] in {"1.", "2.", "3.", "4.", "5."}
        ]
        assert len(numbered) == 4

    def test_ask_only_unresolved_dimensions(self):
        assert "Ask only what is still unresolved" in ORCHESTRATOR_DASHBOARD_SCOPING

    def test_all_resolved_means_build_without_asking(self):
        """This is what keeps the flow from becoming a toll booth."""
        assert "ask nothing and build immediately" in ORCHESTRATOR_DASHBOARD_SCOPING

    def test_a_worked_example_of_a_pre_resolved_dimension(self):
        assert "fixes the time range" in ORCHESTRATOR_DASHBOARD_SCOPING


class TestAnswersReachTheDashboardAgent:
    def test_eda_findings_pass_through_is_instructed(self):
        assert "eda_findings" in ORCHESTRATOR_DASHBOARD_SCOPING

    def test_the_users_own_wording_is_preserved(self):
        assert "in their own wording" in ORCHESTRATOR_DASHBOARD_SCOPING

    def test_the_pass_through_reaches_both_consumers(self):
        assert "eda_findings" in _ORCHESTRATOR_CHASSIS
        assert "eda_findings" in _ORCHESTRATOR_IDENTITY


class TestTheNeverAskBanIsScoped:
    def test_the_ban_is_limited_to_ingestion(self):
        tools = DEFAULTS["orchestrator"]["tools"]
        assert "handle the ingestion workflow automatically" in tools

    def test_the_ban_disclaims_scoping_questions(self):
        tools = DEFAULTS["orchestrator"]["tools"]
        assert "does not stop you from asking scoping questions" in tools

    def test_the_old_blanket_wording_is_gone(self):
        tools = DEFAULTS["orchestrator"]["tools"]
        assert "You MUST handle the full workflow automatically." not in tools


class TestChartRoutingReachesEveryPromptPath:
    """The chart tools are bound in all three paths (graph.build_orchestrator_tools),
    so a guide that omits them mis-routes ad-hoc chart requests into create_dashboard
    — which is what happened before this branch, in the seeded profile text."""

    def test_the_seeded_tool_guide_routes_charts(self):
        tools = DEFAULTS["orchestrator"]["tools"]
        assert "generate_chat_chart" in tools
        assert "select_dashboard_widget" in tools
        assert "Requests to create dashboards or visualizations" not in tools

    def test_the_legacy_hardcoded_guide_routes_charts(self):
        from backend.agents.orchestrator.prompts import build_orchestrator_prompt

        prompt = build_orchestrator_prompt(None)
        assert "generate_chat_chart" in prompt
        assert "select_dashboard_widget" in prompt

    def test_the_lean_guide_routes_charts(self):
        from backend.agents.orchestrator.prompts import _LEAN_ROUTING_RULE

        assert "generate_chat_chart" in _LEAN_ROUTING_RULE
        assert "select_dashboard_widget" in _LEAN_ROUTING_RULE

    def test_the_mention_routing_bias_agrees_with_the_tool_guide(self):
        """The bias block is appended after the guide, so a contradiction there
        wins: it must not send an @dashboard chart request to a non-chart verb."""
        from backend.agents.orchestrator.prompts import render_mentions_block
        from backend.schemas.chat import ResolvedMention

        block = render_mentions_block([
            ResolvedMention(type="dashboard", id=1, name="d", display_name="D"),
        ])
        assert "select_dashboard_widget" in block
