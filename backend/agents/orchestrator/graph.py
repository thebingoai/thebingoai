from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from backend.agents.orchestrator.prompts import build_orchestrator_prompt
from backend.agents.data_agent import invoke_data_agent
from backend.agents.rag_agent import invoke_rag_agent
from backend.agents.skills import get_skill_registry
from backend.agents.context import AgentContext
from backend.agents.tool_registry import build_tools_for_keys
from backend.agents.dashboard_agent import invoke_dashboard_agent
from backend.llm.factory import get_provider
from backend.config import settings
from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING
import json
import logging
import time

if TYPE_CHECKING:
    from backend.models.custom_agent import CustomAgent
    from backend.models.user_skill import UserSkill

logger = logging.getLogger(__name__)


def _friendly_error(e: Exception) -> str:
    """Return a user-friendly warning message for known LLM API errors."""
    msg = str(e)
    if "insufficient_quota" in msg or "exceeded your current quota" in msg:
        return (
            "⚠️ The AI service is temporarily unavailable — the API quota has been exceeded. "
            "Please check your billing details or try again later."
        )
    if "context_length_exceeded" in msg or "maximum context length" in msg:
        return (
            "⚠️ This conversation has become too long for the AI to process. "
            "Please start a new conversation to continue."
        )
    if "rate_limit" in msg or "Rate limit" in msg or ("429" in msg and "insufficient_quota" not in msg):
        return (
            "⚠️ The AI service is rate-limited right now. Please wait a moment and try again."
        )
    if "401" in msg or "invalid_api_key" in msg or "Incorrect API key" in msg:
        return (
            "⚠️ The AI service API key is invalid or missing. "
            "Please check your configuration."
        )
    # Unknown error — keep message but strip raw dict noise
    return f"⚠️ Something went wrong: {msg}"


def _build_dashboard_agent_tool(context: AgentContext, db_session_factory: Optional[Callable] = None) -> List:
    """Return [dashboard_agent] tool when db_session_factory is available."""
    if db_session_factory is None:
        return []

    @tool
    async def dashboard_agent(request: str) -> str:
        """
        Create a persistent dashboard from a natural language request.

        This agent autonomously explores the database schema, designs the layout,
        generates valid SQL queries, and creates the dashboard. Use when the user
        asks to create, build, or make a dashboard.

        Args:
            request: Natural language description of the dashboard to create

        Returns:
            JSON string with success, dashboard_id, message, and steps
        """
        result = await invoke_dashboard_agent(request, context, db_session_factory)
        return json.dumps(result)

    return [dashboard_agent]


def _build_dashboard_plan_tool() -> List:
    """Return [propose_dashboard_plan] tool — a marker tool that triggers approval UI."""

    @tool
    async def propose_dashboard_plan(plan_markdown: str) -> str:
        """
        Present a structured dashboard plan to the user for approval before creation.

        Call this after gathering requirements to show the user a structured plan.
        Wait for the user to approve or request revisions before calling dashboard_agent.

        Args:
            plan_markdown: The full dashboard plan in markdown format

        Returns:
            JSON indicating the plan is awaiting user approval
        """
        return json.dumps({"success": True, "plan": plan_markdown, "awaiting_approval": True})

    return [propose_dashboard_plan]


def build_orchestrator_tools(
    context: AgentContext,
    custom_agents: Optional[List["CustomAgent"]] = None,
    db_session_factory: Optional[Callable] = None,
    user_skills: Optional[List["UserSkill"]] = None,
):
    """
    Build orchestrator tools.

    When custom_agents is provided, each custom agent is wrapped as a
    single tool for the orchestrator to invoke. Runtime enforcement filters out
    tools and connections that are no longer in the team's policy.

    When custom_agents is None or empty, falls back to the legacy static tools
    (data_agent, rag_agent, recall_memory + skills) for backward compatibility.

    db_session_factory is passed through to _build_skill_tools() so the
    orchestrator can create/list/use/delete skills during a conversation.
    """
    skill_tools = _build_skill_tools(context, user_skills, db_session_factory)
    soul_tools = _build_soul_tools(context, db_session_factory)
    dashboard_tools = _build_dashboard_agent_tool(context, db_session_factory)
    plan_tools = _build_dashboard_plan_tool()
    if custom_agents:
        return _build_dynamic_tools(context, custom_agents) + skill_tools + soul_tools + dashboard_tools + plan_tools
    return _build_legacy_tools(context, db_session_factory) + skill_tools + soul_tools + plan_tools


def _build_skill_tools(
    context: AgentContext,
    user_skills: Optional[List["UserSkill"]] = None,
    db_session_factory: Optional[Callable] = None,
) -> List:
    """
    Build tools that allow the orchestrator to create, list, use, and delete user skills.

    Tools are no-ops (returning an informative error) when db_session_factory is not provided.
    """
    if db_session_factory is None:
        return []

    @tool
    async def create_skill(
        name: str,
        description: str,
        instructions: str = "",
        prompt_template: str = "",
        code: str = "",
        parameters_schema: str = "",
        secrets: str = "",
        activation_hint: str = "",
        references: str = "",
    ) -> str:
        """
        Create a new reusable skill with progressive disclosure support.

        Skill type is auto-determined:
        - instructions + code → hybrid
        - instructions only → instruction
        - code (with or without prompt_template) → code
        - prompt_template only → prompt

        Args:
            name: Unique snake_case name (e.g. "get_property_listings")
            description: What this skill does (used for routing decisions)
            instructions: Rich Markdown workflow, domain expertise, or decision tree (for instruction/hybrid skills)
            prompt_template: Formatting instructions the LLM follows when using this skill
            code: Python async function body. Must define `async def run()`. May use params/secrets globals.
            parameters_schema: JSON object mapping param names to types (e.g. '{"region": "str"}')
            secrets: JSON object of secret key-value pairs (e.g. '{"api_key": "sk-..."}')
            activation_hint: Optional hint for better skill discovery (e.g. "Use when user asks about SEO")
            references: JSON array of {"title": "...", "content": "..."} reference documents

        Returns:
            JSON with success status and skill details
        """
        from backend.models.user_skill import UserSkill as UserSkillModel
        from backend.models.skill_reference import SkillReference as SkillReferenceModel
        import uuid

        # Auto-determine skill_type
        if instructions and code:
            skill_type = "hybrid"
        elif instructions:
            skill_type = "instruction"
        elif code:
            skill_type = "code"
        else:
            skill_type = "prompt"

        db = db_session_factory()
        try:
            # Check for any existing record (active or soft-deleted)
            existing = db.query(UserSkillModel).filter(
                UserSkillModel.user_id == context.user_id,
                UserSkillModel.name == name,
            ).first()
            if existing and existing.is_active:
                return json.dumps({
                    "success": False,
                    "message": f"A skill named '{name}' already exists. Use a different name or delete the existing one first.",
                })

            parsed_schema = None
            if parameters_schema:
                try:
                    parsed_schema = json.loads(parameters_schema)
                except json.JSONDecodeError:
                    return json.dumps({"success": False, "message": "parameters_schema must be valid JSON"})

            parsed_secrets = None
            if secrets:
                try:
                    parsed_secrets = json.loads(secrets)
                except json.JSONDecodeError:
                    return json.dumps({"success": False, "message": "secrets must be valid JSON"})

            parsed_references = []
            if references:
                try:
                    parsed_references = json.loads(references)
                    if not isinstance(parsed_references, list):
                        return json.dumps({"success": False, "message": "references must be a JSON array"})
                except json.JSONDecodeError:
                    return json.dumps({"success": False, "message": "references must be valid JSON array"})

            if existing:
                # Reactivate and update the soft-deleted record
                existing.description = description
                existing.instructions = instructions or None
                existing.prompt_template = prompt_template or None
                existing.code = code or None
                existing.parameters_schema = parsed_schema
                existing.secrets = parsed_secrets
                existing.skill_type = skill_type
                existing.activation_hint = activation_hint or None
                existing.is_active = True
                existing.version = (existing.version or 1) + 1
                skill = existing
            else:
                skill = UserSkillModel(
                    id=str(uuid.uuid4()),
                    user_id=context.user_id,
                    name=name,
                    description=description,
                    instructions=instructions or None,
                    prompt_template=prompt_template or None,
                    code=code or None,
                    parameters_schema=parsed_schema,
                    secrets=parsed_secrets,
                    skill_type=skill_type,
                    activation_hint=activation_hint or None,
                    is_active=True,
                    version=1,
                )
                db.add(skill)

            db.flush()

            # Add references
            for i, ref in enumerate(parsed_references):
                ref_obj = SkillReferenceModel(
                    id=str(uuid.uuid4()),
                    skill_id=skill.id,
                    title=ref.get("title", f"Reference {i+1}"),
                    content=ref.get("content", ""),
                    sort_order=i,
                )
                db.add(ref_obj)

            db.commit()
            db.refresh(skill)
            return json.dumps({
                "success": True,
                "message": f"Skill '{name}' created successfully.",
                "skill_id": skill.id,
                "skill_type": skill_type,
                "has_code": bool(code),
                "has_instructions": bool(instructions),
                "has_prompt_template": bool(prompt_template),
                "reference_count": len(parsed_references),
            })
        except Exception as exc:
            db.rollback()
            logger.error(f"create_skill failed: {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    @tool
    async def activate_skill(skill_name: str) -> str:
        """
        Load a skill's full content before using it. REQUIRED before first use.

        Returns instructions, code status, prompt template, reference list, and usage guidance.

        Args:
            skill_name: Exact name of the skill to activate

        Returns:
            JSON with full skill content and usage guidance
        """
        from backend.models.user_skill import UserSkill as UserSkillModel
        from backend.models.skill_reference import SkillReference as SkillReferenceModel
        from sqlalchemy.orm import joinedload

        db = db_session_factory()
        try:
            skill = db.query(UserSkillModel).options(
                joinedload(UserSkillModel.references)
            ).filter(
                UserSkillModel.user_id == context.user_id,
                UserSkillModel.name == skill_name,
                UserSkillModel.is_active == True,
            ).first()

            if not skill:
                return json.dumps({"success": False, "message": f"No active skill named '{skill_name}' found"})

            ref_titles = [r.title for r in sorted(skill.references, key=lambda r: r.sort_order)] if skill.references else []

            skill_type = skill.skill_type or "code"
            if skill_type == "instruction":
                guidance = "This is an instruction skill. Follow the instructions directly to fulfill the user's request. Do NOT call use_skill."
            elif skill_type == "hybrid":
                guidance = "This is a hybrid skill. Follow the instructions, then call use_skill for the code parts."
            elif skill_type == "prompt":
                guidance = "This is a prompt skill. Apply the prompt_template to format the relevant data."
            else:
                guidance = "This is a code skill. Call use_skill to execute it."

            return json.dumps({
                "success": True,
                "skill_name": skill_name,
                "skill_type": skill_type,
                "instructions": skill.instructions,
                "prompt_template": skill.prompt_template,
                "has_code": bool(skill.code),
                "parameters_schema": skill.parameters_schema,
                "references": ref_titles,
                "guidance": guidance,
            })
        except Exception as exc:
            logger.error(f"activate_skill failed for '{skill_name}': {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    @tool
    async def list_my_skills() -> str:
        """
        List all your active skills with their names, types, and descriptions.

        Returns:
            JSON array of active skills
        """
        from backend.models.user_skill import UserSkill as UserSkillModel

        db = db_session_factory()
        try:
            skills = db.query(UserSkillModel).filter(
                UserSkillModel.user_id == context.user_id,
                UserSkillModel.is_active == True,
            ).all()
            return json.dumps({
                "success": True,
                "skills": [
                    {
                        "name": s.name,
                        "description": s.description,
                        "skill_type": s.skill_type or "code",
                        "has_instructions": s.instructions is not None,
                        "has_code": s.code is not None,
                        "has_prompt_template": s.prompt_template is not None,
                        "parameters_schema": s.parameters_schema,
                    }
                    for s in skills
                ],
            })
        except Exception as exc:
            logger.error(f"list_my_skills failed: {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    @tool
    async def use_skill(skill_name: str, params_json: str = "{}") -> str:
        """
        Execute a previously created skill. Call activate_skill first to load the skill.

        For instruction-only skills, use activate_skill and follow the instructions instead.

        Args:
            skill_name: Exact name of the skill to run
            params_json: JSON object of parameters to pass to the skill (e.g. '{"region": "Dublin"}')

        Returns:
            The skill's output or instructions to follow
        """
        from backend.models.user_skill import UserSkill as UserSkillModel
        from backend.agents.skills.executor import execute_skill_code

        db = db_session_factory()
        try:
            skill = db.query(UserSkillModel).filter(
                UserSkillModel.user_id == context.user_id,
                UserSkillModel.name == skill_name,
                UserSkillModel.is_active == True,
            ).first()
            if not skill:
                return json.dumps({"success": False, "message": f"No active skill named '{skill_name}' found"})

            # Handle instruction-only skills
            skill_type = skill.skill_type or "code"
            if skill_type == "instruction" and not skill.code:
                return json.dumps({
                    "success": True,
                    "skill_type": "instruction",
                    "instructions": skill.instructions,
                    "message": "Follow these instructions to fulfill the request. Do not call use_skill for instruction skills.",
                })

            try:
                params = json.loads(params_json) if params_json else {}
            except json.JSONDecodeError:
                return json.dumps({"success": False, "message": "params_json must be valid JSON"})

            raw_output = None

            # Execute code if present
            if skill.code:
                result = await execute_skill_code(
                    code=skill.code,
                    params=params,
                    secrets=skill.secrets or {},
                )
                if isinstance(result, dict) and "error" in result:
                    return json.dumps({"success": False, "message": result["error"]})
                raw_output = result

            # Format using prompt_template via LLM if we have both
            if skill.prompt_template and raw_output is not None:
                provider = get_provider(settings.default_llm_provider)
                format_messages = [
                    {
                        "role": "system",
                        "content": skill.prompt_template,
                    },
                    {
                        "role": "user",
                        "content": f"Data to format:\n{json.dumps(raw_output, default=str)}",
                    },
                ]
                formatted = await provider.chat(format_messages, temperature=0.3)
                return json.dumps({"success": True, "result": formatted, "raw": raw_output})

            # Only prompt_template, no code — return template as instructions
            if skill.prompt_template and raw_output is None:
                return json.dumps({
                    "success": True,
                    "prompt_template": skill.prompt_template,
                    "message": "Apply this template to the relevant data.",
                })

            # Only code, no prompt_template — return raw output
            if raw_output is not None:
                return json.dumps({"success": True, "result": raw_output})

            return json.dumps({"success": False, "message": "Skill has neither code nor a prompt template"})

        except Exception as exc:
            logger.error(f"use_skill failed for '{skill_name}': {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    @tool
    async def read_skill_reference(skill_name: str, reference_title: str) -> str:
        """
        Load a specific reference document from a skill. Use when activate_skill shows references.

        Args:
            skill_name: Exact name of the skill
            reference_title: Exact title of the reference to load

        Returns:
            JSON with the reference content
        """
        from backend.models.user_skill import UserSkill as UserSkillModel
        from backend.models.skill_reference import SkillReference as SkillReferenceModel

        db = db_session_factory()
        try:
            skill = db.query(UserSkillModel).filter(
                UserSkillModel.user_id == context.user_id,
                UserSkillModel.name == skill_name,
                UserSkillModel.is_active == True,
            ).first()
            if not skill:
                return json.dumps({"success": False, "message": f"No active skill named '{skill_name}' found"})

            ref = db.query(SkillReferenceModel).filter(
                SkillReferenceModel.skill_id == skill.id,
                SkillReferenceModel.title == reference_title,
            ).first()
            if not ref:
                return json.dumps({"success": False, "message": f"No reference titled '{reference_title}' found in skill '{skill_name}'"})

            return json.dumps({
                "success": True,
                "skill_name": skill_name,
                "reference_title": reference_title,
                "content": ref.content,
            })
        except Exception as exc:
            logger.error(f"read_skill_reference failed: {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    @tool
    async def update_skill(
        skill_name: str,
        description: str = "",
        instructions: str = "",
        prompt_template: str = "",
        code: str = "",
        parameters_schema: str = "",
        activation_hint: str = "",
        add_references: str = "",
        remove_reference_titles: str = "",
    ) -> str:
        """
        Update an existing skill's content. Only provided fields are updated. Increments version.

        Args:
            skill_name: Exact name of the skill to update
            description: New description (leave empty to keep current)
            instructions: New Markdown instructions (leave empty to keep current)
            prompt_template: New prompt template (leave empty to keep current)
            code: New Python code (leave empty to keep current)
            parameters_schema: New JSON parameters schema (leave empty to keep current)
            activation_hint: New activation hint (leave empty to keep current)
            add_references: JSON array of {"title": "...", "content": "..."} to add
            remove_reference_titles: JSON array of reference titles to remove

        Returns:
            JSON with success status and updated version number
        """
        from backend.models.user_skill import UserSkill as UserSkillModel
        from backend.models.skill_reference import SkillReference as SkillReferenceModel
        import uuid

        db = db_session_factory()
        try:
            skill = db.query(UserSkillModel).filter(
                UserSkillModel.user_id == context.user_id,
                UserSkillModel.name == skill_name,
                UserSkillModel.is_active == True,
            ).first()
            if not skill:
                return json.dumps({"success": False, "message": f"No active skill named '{skill_name}' found"})

            if description:
                skill.description = description
            if instructions:
                skill.instructions = instructions
            if prompt_template:
                skill.prompt_template = prompt_template
            if code:
                skill.code = code
            if activation_hint:
                skill.activation_hint = activation_hint
            if parameters_schema:
                try:
                    skill.parameters_schema = json.loads(parameters_schema)
                except json.JSONDecodeError:
                    return json.dumps({"success": False, "message": "parameters_schema must be valid JSON"})

            # Recalculate skill_type
            has_instructions = bool(skill.instructions)
            has_code = bool(skill.code)
            if has_instructions and has_code:
                skill.skill_type = "hybrid"
            elif has_instructions:
                skill.skill_type = "instruction"
            elif has_code:
                skill.skill_type = "code"
            else:
                skill.skill_type = "prompt"

            # Remove references
            if remove_reference_titles:
                try:
                    titles_to_remove = json.loads(remove_reference_titles)
                    db.query(SkillReferenceModel).filter(
                        SkillReferenceModel.skill_id == skill.id,
                        SkillReferenceModel.title.in_(titles_to_remove),
                    ).delete(synchronize_session=False)
                except json.JSONDecodeError:
                    return json.dumps({"success": False, "message": "remove_reference_titles must be a JSON array"})

            # Add new references
            if add_references:
                try:
                    new_refs = json.loads(add_references)
                    existing_count = db.query(SkillReferenceModel).filter(
                        SkillReferenceModel.skill_id == skill.id
                    ).count()
                    for i, ref in enumerate(new_refs):
                        ref_obj = SkillReferenceModel(
                            id=str(uuid.uuid4()),
                            skill_id=skill.id,
                            title=ref.get("title", f"Reference {existing_count + i + 1}"),
                            content=ref.get("content", ""),
                            sort_order=existing_count + i,
                        )
                        db.add(ref_obj)
                except json.JSONDecodeError:
                    return json.dumps({"success": False, "message": "add_references must be a JSON array"})

            skill.version = (skill.version or 1) + 1
            db.commit()

            return json.dumps({
                "success": True,
                "message": f"Skill '{skill_name}' updated to version {skill.version}.",
                "skill_type": skill.skill_type,
                "version": skill.version,
            })
        except Exception as exc:
            db.rollback()
            logger.error(f"update_skill failed: {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    @tool
    async def delete_skill(skill_name: str) -> str:
        """
        Delete (deactivate) a skill that is no longer needed.

        Args:
            skill_name: Exact name of the skill to delete

        Returns:
            JSON with success status
        """
        from backend.models.user_skill import UserSkill as UserSkillModel

        db = db_session_factory()
        try:
            skill = db.query(UserSkillModel).filter(
                UserSkillModel.user_id == context.user_id,
                UserSkillModel.name == skill_name,
                UserSkillModel.is_active == True,
            ).first()
            if not skill:
                return json.dumps({"success": False, "message": f"No active skill named '{skill_name}' found"})
            skill.is_active = False
            db.commit()
            return json.dumps({"success": True, "message": f"Skill '{skill_name}' has been deleted"})
        except Exception as exc:
            db.rollback()
            logger.error(f"delete_skill failed: {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    @tool
    async def check_skill_suggestions() -> str:
        """
        Check for pending skill suggestions detected by background analysis.

        Call this at the start of each conversation to surface patterns the system detected.

        Returns:
            JSON with up to 3 pending suggestions
        """
        from backend.models.skill_suggestion import SkillSuggestion as SkillSuggestionModel

        db = db_session_factory()
        try:
            suggestions = db.query(SkillSuggestionModel).filter(
                SkillSuggestionModel.user_id == context.user_id,
                SkillSuggestionModel.status == "pending",
            ).order_by(SkillSuggestionModel.confidence.desc()).limit(3).all()

            return json.dumps({
                "success": True,
                "suggestions": [
                    {
                        "id": s.id,
                        "suggested_name": s.suggested_name,
                        "suggested_description": s.suggested_description,
                        "suggested_skill_type": s.suggested_skill_type,
                        "pattern_summary": s.pattern_summary,
                        "confidence": s.confidence,
                    }
                    for s in suggestions
                ],
            })
        except Exception as exc:
            logger.error(f"check_skill_suggestions failed: {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    @tool
    async def respond_to_skill_suggestion(suggestion_id: str, action: str) -> str:
        """
        Accept or dismiss a background-detected skill suggestion.

        Args:
            suggestion_id: ID of the suggestion (from check_skill_suggestions)
            action: "accept" to create the skill, "dismiss" to decline

        Returns:
            JSON with success status
        """
        from backend.models.skill_suggestion import SkillSuggestion as SkillSuggestionModel
        from backend.models.user_skill import UserSkill as UserSkillModel
        import uuid

        if action not in ("accept", "dismiss"):
            return json.dumps({"success": False, "message": "action must be 'accept' or 'dismiss'"})

        db = db_session_factory()
        try:
            suggestion = db.query(SkillSuggestionModel).filter(
                SkillSuggestionModel.id == suggestion_id,
                SkillSuggestionModel.user_id == context.user_id,
            ).first()
            if not suggestion:
                return json.dumps({"success": False, "message": "Suggestion not found"})

            if action == "accept":
                new_skill = UserSkillModel(
                    id=str(uuid.uuid4()),
                    user_id=context.user_id,
                    name=suggestion.suggested_name,
                    description=suggestion.suggested_description or "",
                    skill_type=suggestion.suggested_skill_type or "instruction",
                    instructions=suggestion.suggested_instructions,
                    is_active=True,
                    version=1,
                )
                db.add(new_skill)
                suggestion.status = "accepted"
                message = f"Skill '{suggestion.suggested_name}' created from suggestion."
            else:
                suggestion.status = "dismissed"
                message = "Suggestion dismissed."

            db.commit()
            return json.dumps({"success": True, "message": message})
        except Exception as exc:
            db.rollback()
            logger.error(f"respond_to_skill_suggestion failed: {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    return [
        create_skill, activate_skill, list_my_skills, use_skill,
        read_skill_reference, update_skill, delete_skill,
        check_skill_suggestions, respond_to_skill_suggestion,
    ]


def _build_soul_tools(
    context: AgentContext,
    db_session_factory: Optional[Callable] = None,
) -> List:
    """
    Build tools for the orchestrator to propose and apply soul updates.

    propose_soul_update: Stages a soul proposal for user review (no DB write).
    apply_soul_update: Persists the soul to the DB after user confirms.
    """
    if db_session_factory is None:
        return []

    @tool
    async def propose_soul_update(proposed_soul: str, reason: str) -> str:
        """
        Propose an update to your soul — the personalized prompt that shapes your behavior for this user.

        This does NOT apply the update automatically. Present the proposal to the user and wait for
        explicit confirmation before calling apply_soul_update.

        Args:
            proposed_soul: The full updated soul text (under 500 words)
            reason: Why you're proposing this change

        Returns:
            Formatted proposal ready to present to the user
        """
        word_count = len(proposed_soul.split())
        if word_count > 600:
            return json.dumps({
                "success": False,
                "message": f"Soul is too long ({word_count} words). Keep it under 500 words."
            })
        proposal = (
            f"I'd like to update my soul — the part of my personality that shapes how I work with you.\n\n"
            f"**Why:** {reason}\n\n"
            f"**Proposed soul:**\n---\n{proposed_soul}\n---\n\n"
            f"Would you like me to apply this?"
        )
        return json.dumps({"success": True, "proposal": proposal, "proposed_soul": proposed_soul})

    @tool
    async def apply_soul_update(proposed_soul: str) -> str:
        """
        Apply a soul update that the user has explicitly approved.

        Only call this after the user has confirmed the proposal from propose_soul_update.

        Args:
            proposed_soul: The soul text to save (must match what was proposed)

        Returns:
            JSON with success status and new version number
        """
        db = db_session_factory()
        try:
            from backend.models.user import User as UserModel
            user = db.query(UserModel).filter(UserModel.id == context.user_id).first()
            if not user:
                return json.dumps({"success": False, "message": "User not found"})
            user.soul_prompt = proposed_soul
            user.soul_version = (user.soul_version or 0) + 1
            db.commit()
            return json.dumps({
                "success": True,
                "message": "Soul updated successfully.",
                "soul_version": user.soul_version,
            })
        except Exception as exc:
            db.rollback()
            logger.error(f"apply_soul_update failed: {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    return [propose_soul_update, apply_soul_update]


def _build_legacy_tools(context: AgentContext, db_session_factory: Optional[Callable] = None):
    """Legacy static tools used when no custom agents are configured."""

    @tool
    async def data_agent(question: str) -> str:
        """
        Query databases using SQL. Use for data analysis questions.

        Args:
            question: Natural language question about data

        Returns:
            JSON string with SQL queries and results
        """
        result = await invoke_data_agent(question, context)
        return json.dumps(result)

    @tool
    async def rag_agent(question: str, namespace: str = "default") -> str:
        """
        Search uploaded documents. Use for questions about documentation.

        Args:
            question: Question about documents
            namespace: Vector namespace (default: "default")

        Returns:
            JSON string with answer and source context
        """
        result = await invoke_rag_agent(question, context, namespace)
        return json.dumps(result)

    @tool
    async def recall_memory(query: str) -> str:
        """
        Recall past conversation context and patterns.

        Args:
            query: What to recall — topics, tables, patterns, past questions

        Returns:
            JSON with relevant past interactions or empty if none found
        """
        from backend.memory.retriever import MemoryRetriever
        retriever = MemoryRetriever()
        context_str = await retriever.get_relevant_context(
            user_id=context.user_id, query=query, top_k=5
        )
        if not context_str:
            return json.dumps({"success": True, "memories": [], "message": "No relevant memories found"})
        return json.dumps({"success": True, "memories": context_str})

    # Get skills from registry
    skill_tools = get_skill_registry().to_tools()

    return [data_agent, rag_agent, recall_memory] + skill_tools + _build_dashboard_agent_tool(context, db_session_factory)


def _build_dynamic_tools(context: AgentContext, custom_agents: List["CustomAgent"]) -> List:
    """
    Build one tool per custom agent definition.

    Each custom agent is wrapped as a single callable tool. At build time the
    effective tool set is computed by intersecting the agent's stored tool_keys
    with the team's current allowed_tool_keys (runtime enforcement).
    """
    provider = get_provider(settings.default_llm_provider)
    tools = []

    for agent_def in custom_agents:
        # Runtime enforcement: intersect stored keys with current team policy
        effective_tool_keys = [
            k for k in (agent_def.tool_keys or [])
            if context.can_use_tool(k)
        ]
        if agent_def.connection_ids:
            effective_connection_ids = [
                c for c in agent_def.connection_ids
                if context.can_access_connection(c)
            ]
        else:
            # No explicit connections configured — inherit parent's accessible connections
            effective_connection_ids = list(context.available_connections)

        # Scoped context for this sub-agent
        agent_context = AgentContext(
            user_id=context.user_id,
            available_connections=effective_connection_ids,
            thread_id=context.thread_id,
            team_id=context.team_id,
            allowed_tool_keys=effective_tool_keys,
        )

        # Build the concrete LangChain tools for this agent
        agent_tools = build_tools_for_keys(effective_tool_keys, agent_context)

        agent_name = agent_def.name
        # Sanitize to match OpenAI tool name pattern: ^[a-zA-Z0-9_-]+$
        import re as _re
        tool_name = _re.sub(r'[^a-zA-Z0-9_-]', '_', agent_name)
        agent_description = agent_def.description or f"Custom agent: {agent_name}"
        agent_system_prompt = agent_def.system_prompt

        @tool(tool_name, description=agent_description)
        async def invoke_custom_agent(
            question: str,
            _system_prompt: str = agent_system_prompt,
            _tools: list = agent_tools,
            _ctx: AgentContext = agent_context,
        ) -> str:
            """Invoke a custom sub-agent with its configured tools."""
            sub_agent = create_react_agent(
                model=provider.get_langchain_llm(),
                tools=_tools,
                prompt=_system_prompt,
            )
            try:
                result = await sub_agent.ainvoke({"messages": [HumanMessage(content=question)]})
                messages = result.get("messages", [])
                final_answer = None
                for msg in reversed(messages):
                    if hasattr(msg, "type") and msg.type == "ai" and not getattr(msg, "tool_calls", None):
                        final_answer = msg.content
                        break
                return json.dumps({"success": True, "message": final_answer or "Completed"})
            except Exception as exc:
                logger.error(f"Custom agent '{agent_name}' failed: {exc}")
                return json.dumps({"success": False, "message": str(exc)})

        tools.append(invoke_custom_agent)

    return tools


async def run_orchestrator(
    user_question: str,
    context: AgentContext,
    history: list = None,
    custom_agents: Optional[List["CustomAgent"]] = None,
    db_session_factory: Optional[Callable] = None,
    memory_context: str = "",
    user_skills: Optional[List["UserSkill"]] = None,
    user_memories_context: str = "",
    skill_suggestions: Optional[list] = None,
    soul_prompt: str = "",
) -> Dict[str, Any]:
    """
    Run orchestrator agent (non-streaming).

    Args:
        user_question: User's natural language question
        context: AgentContext with user_id, available_connections, thread_id
        custom_agents: Optional list of active CustomAgent records for this user
        db_session_factory: Optional callable returning a SQLAlchemy Session (for skill tools)
        memory_context: Optional pre-fetched memory context string to prepend to the system prompt
        user_skills: Optional list of active UserSkill records for this user
        user_memories_context: Optional user-directed memories to inject as instructions
        skill_suggestions: Optional list of pending skill suggestions to surface
        soul_prompt: Optional per-user soul text to inject into the orchestrator prompt

    Returns:
        Dict with success, message, metadata
    """
    tools = build_orchestrator_tools(context, custom_agents, db_session_factory, user_skills)
    prompt = build_orchestrator_prompt(custom_agents, memory_context=memory_context, user_skills=user_skills, user_memories_context=user_memories_context, skill_suggestions=skill_suggestions, soul_prompt=soul_prompt, available_connections=context.available_connections)

    provider = get_provider(settings.default_llm_provider)

    orchestrator = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        prompt=prompt,
    )

    try:
        messages = []
        if history:
            for msg in history:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=user_question))

        if not soul_prompt:
            if not history:
                messages.insert(0, SystemMessage(content=(
                    "IMPORTANT: Your soul is empty — this is your first conversation with this user. "
                    "You have no name or personality yet. Introduce yourself as a new assistant that can be personalized. "
                    "Invite the user to give you a name and describe how they'd like you to behave. "
                    "If they skip it, proceed normally — don't push."
                )))
            else:
                messages.insert(0, SystemMessage(content=(
                    "IMPORTANT: Your soul is still empty. If the user has provided a name, preferences, "
                    "or personality instructions in this conversation, you MUST call propose_soul_update "
                    "to capture them. Do NOT just acknowledge verbally — use the tool to persist it."
                )))

        result = await orchestrator.ainvoke({"messages": messages})

        messages = result.get("messages", [])

        final_answer = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and not getattr(msg, "tool_calls", None):
                final_answer = msg.content
                break

        return {
            "success": True,
            "message": final_answer or "Query completed successfully",
            "thread_id": context.thread_id
        }

    except Exception as e:
        logger.error(f"Orchestrator failed: {str(e)}")
        return {
            "success": False,
            "message": _friendly_error(e),
            "thread_id": context.thread_id
        }


async def stream_orchestrator(
    user_question: str,
    context: AgentContext,
    history: list = None,
    custom_agents: Optional[List["CustomAgent"]] = None,
    db_session_factory: Optional[Callable] = None,
    memory_context: str = "",
    user_skills: Optional[List["UserSkill"]] = None,
    user_memories_context: str = "",
    skill_suggestions: Optional[list] = None,
    soul_prompt: str = "",
):
    """
    Stream orchestrator responses using SSE event format.

    Args:
        user_question: User's natural language question
        context: AgentContext with user_id, available_connections, thread_id
        custom_agents: Optional list of active CustomAgent records for this user
        db_session_factory: Optional callable returning a SQLAlchemy Session (for skill tools)
        memory_context: Optional pre-fetched memory context string to prepend to the system prompt
        user_skills: Optional list of active UserSkill records for this user
        user_memories_context: Optional user-directed memories to inject as instructions
        skill_suggestions: Optional list of pending skill suggestions to surface
        soul_prompt: Optional per-user soul text to inject into the orchestrator prompt

    Yields:
        SSE events: {"type": "status|token|done|error", "content": ...}
    """
    try:
        yield {"type": "status", "content": "Starting orchestrator..."}

        tools = build_orchestrator_tools(context, custom_agents, db_session_factory, user_skills)
        prompt = build_orchestrator_prompt(custom_agents, memory_context=memory_context, user_skills=user_skills, user_memories_context=user_memories_context, skill_suggestions=skill_suggestions, soul_prompt=soul_prompt, available_connections=context.available_connections)

        provider = get_provider(settings.default_llm_provider)

        orchestrator = create_react_agent(
            model=provider.get_langchain_llm(),
            tools=tools,
            prompt=prompt,
        )

        messages = []
        if history:
            for msg in history:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=user_question))

        if not soul_prompt:
            if not history:
                messages.insert(0, SystemMessage(content=(
                    "IMPORTANT: Your soul is empty — this is your first conversation with this user. "
                    "You have no name or personality yet. Introduce yourself as a new assistant that can be personalized. "
                    "Invite the user to give you a name and describe how they'd like you to behave. "
                    "If they skip it, proceed normally — don't push."
                )))
            else:
                messages.insert(0, SystemMessage(content=(
                    "IMPORTANT: Your soul is still empty. If the user has provided a name, preferences, "
                    "or personality instructions in this conversation, you MUST call propose_soul_update "
                    "to capture them. Do NOT just acknowledge verbally — use the tool to persist it."
                )))

        collected_steps = []
        step_number = 0
        step_start_times: Dict[str, float] = {}
        token_buffer = []
        active_stream_run_id = None

        async for event in orchestrator.astream_events(
            {"messages": messages},
            version="v2"
        ):
            kind = event.get("event")

            if kind == "on_tool_start":
                token_buffer.clear()
                active_stream_run_id = None
                tool_name = event.get("name")
                tool_input = event.get("data", {}).get("input", {})
                step_start_times[tool_name] = time.time()
                step_number += 1
                step = {
                    "agent_type": "orchestrator",
                    "step_type": "tool_call",
                    "tool_name": tool_name,
                    "content": {"tool": tool_name, "args": tool_input},
                    "step_number": step_number
                }
                collected_steps.append(step)
                yield {
                    "type": "tool_call",
                    "content": {"tool": tool_name, "status": "started", "args": tool_input}
                }

            elif kind == "on_tool_end":
                token_buffer.clear()
                active_stream_run_id = None
                tool_name = event.get("name")
                tool_output = event.get("data", {}).get("output", None)

                start_time = step_start_times.pop(tool_name, None)
                duration_ms = int((time.time() - start_time) * 1000) if start_time is not None else None

                if hasattr(tool_output, "content"):
                    tool_output = tool_output.content

                parsed_output = None
                if isinstance(tool_output, str):
                    try:
                        parsed_output = json.loads(tool_output)
                    except (json.JSONDecodeError, TypeError):
                        parsed_output = tool_output
                elif tool_output is not None:
                    try:
                        json.dumps(tool_output)
                        parsed_output = tool_output
                    except (TypeError, ValueError):
                        parsed_output = str(tool_output)

                step_number += 1
                step = {
                    "agent_type": "orchestrator",
                    "step_type": "tool_result",
                    "tool_name": tool_name,
                    "content": {"tool": tool_name, "result": parsed_output},
                    "step_number": step_number,
                    "duration_ms": duration_ms
                }
                collected_steps.append(step)
                yield {
                    "type": "tool_result",
                    "content": {"tool": tool_name, "status": "completed", "result": parsed_output, "duration_ms": duration_ms}
                }

            elif kind == "on_chat_model_stream":
                run_id = event.get("run_id")
                if active_stream_run_id is None:
                    active_stream_run_id = run_id
                if run_id != active_stream_run_id:
                    continue
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    content = chunk.content
                    if content:
                        token_buffer.append(content)

        for token in token_buffer:
            yield {"type": "token", "content": token}

        yield {
            "type": "done",
            "content": "Orchestrator completed",
            "thread_id": context.thread_id,
            "steps": collected_steps
        }

    except Exception as e:
        logger.error(f"Orchestrator streaming failed: {str(e)}")
        yield {
            "type": "error",
            "content": _friendly_error(e)
        }
