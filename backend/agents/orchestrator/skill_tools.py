"""
skill_tools.py — Consolidated skill management tools for the orchestrator.

Exposes 5 tools (consolidated from 9):
  manage_skill   — create / update / delete a skill
  get_skill      — activate a skill or load a specific reference document
  use_skill      — execute a code-based skill
  list_skills    — list all active skills
  handle_suggestion — check pending suggestions or accept / dismiss one
"""

from langchain_core.tools import tool
from backend.agents.context import AgentContext
from backend.llm.factory import get_provider
from backend.config import settings
from typing import List, Optional, Callable
import json
import logging

logger = logging.getLogger(__name__)


def build_skill_tools(
    context: AgentContext,
    db_session_factory: Optional[Callable] = None,
) -> List:
    """
    Build the consolidated skill management tools for the orchestrator.

    Returns an empty list when db_session_factory is not provided.

    Args:
        context: Agent execution context (carries user_id and related metadata).
        db_session_factory: Callable that returns a new SQLAlchemy DB session.

    Returns:
        [manage_skill, get_skill, use_skill, list_skills, handle_suggestion]
    """
    if db_session_factory is None:
        return []

    # ------------------------------------------------------------------
    # Tool 1: manage_skill
    # ------------------------------------------------------------------

    @tool
    async def manage_skill(
        action: str,
        # --- create fields ---
        name: str = "",
        description: str = "",
        instructions: str = "",
        prompt_template: str = "",
        code: str = "",
        parameters_schema: str = "",
        secrets: str = "",
        activation_hint: str = "",
        references: str = "",
        # --- update fields ---
        skill_name: str = "",
        add_references: str = "",
        remove_reference_titles: str = "",
    ) -> str:
        """
        Create, update, or delete a skill.

        **Skill types** (auto-determined from provided fields):
        - "instruction" — rich Markdown knowledge, workflows, decision trees. No code runs.
          Use for domain expertise the LLM should reason about directly.
        - "code"        — async Python that calls APIs, queries DBs, or does computation.
          Use when the task needs live data or deterministic logic.
        - "prompt"      — formatting/style template applied via a secondary LLM call.
          Use to standardise output presentation (e.g. tables, reports).
        - "hybrid"      — instructions + code. The LLM follows the instructions, then
          calls use_skill for the code portion.

        The type is inferred automatically:
          instructions + code  → hybrid
          instructions only    → instruction
          code only (± template) → code
          template only        → prompt

        ---

        **action = "create"**
        Required: name, description
        Optional: instructions, code, prompt_template, parameters_schema, secrets,
                  activation_hint, references

        Args:
            name: Unique snake_case identifier (e.g. "get_property_listings").
            description: One-line summary used for routing decisions.
            instructions: Markdown workflow, domain knowledge, or decision tree.
            code: Python async function body. Must define `async def run()`.
                  May reference `params` and `secrets` globals.
            prompt_template: Formatting directive the LLM applies to raw code output.
            parameters_schema: JSON object mapping param names → types
                               (e.g. '{"region": "str", "limit": "int"}').
            secrets: JSON object of secret key-value pairs
                     (e.g. '{"api_key": "sk-..."}').
            activation_hint: Discovery hint (e.g. "Use when the user asks about SEO").
            references: JSON array of {"title": "...", "content": "..."} docs.

        If a soft-deleted skill with the same name exists it is reactivated and
        updated rather than creating a duplicate.

        ---

        **action = "update"**
        Required: skill_name
        Optional: description, instructions, code, prompt_template,
                  parameters_schema, activation_hint,
                  add_references (JSON array), remove_reference_titles (JSON array)

        Only non-empty arguments overwrite the current value.
        skill_type is recalculated from the final state of instructions + code.
        Version is incremented on each update.

        Args:
            skill_name: Exact name of the skill to update.
            add_references: JSON array of {"title": "...", "content": "..."} to append.
            remove_reference_titles: JSON array of reference titles to delete.

        ---

        **action = "delete"**
        Required: skill_name

        Soft-deletes the skill (sets is_active = False). The skill can be
        reactivated later by calling manage_skill with action="create" using the
        same name.

        Args:
            skill_name: Exact name of the skill to delete.

        ---

        Returns:
            JSON with "success" bool and either detail fields (create/update) or
            a "message" string (delete / errors).
        """
        if action == "create":
            return await _create_skill(
                context=context,
                db_session_factory=db_session_factory,
                name=name,
                description=description,
                instructions=instructions,
                prompt_template=prompt_template,
                code=code,
                parameters_schema=parameters_schema,
                secrets=secrets,
                activation_hint=activation_hint,
                references=references,
            )
        elif action == "update":
            return await _update_skill(
                context=context,
                db_session_factory=db_session_factory,
                skill_name=skill_name,
                description=description,
                instructions=instructions,
                prompt_template=prompt_template,
                code=code,
                parameters_schema=parameters_schema,
                activation_hint=activation_hint,
                add_references=add_references,
                remove_reference_titles=remove_reference_titles,
            )
        elif action == "delete":
            return await _delete_skill(
                context=context,
                db_session_factory=db_session_factory,
                skill_name=skill_name,
            )
        else:
            return json.dumps({
                "success": False,
                "message": f"Unknown action '{action}'. Must be 'create', 'update', or 'delete'.",
            })

    # ------------------------------------------------------------------
    # Tool 2: get_skill
    # ------------------------------------------------------------------

    @tool
    async def get_skill(name: str, reference_title: str = "") -> str:
        """
        Load a skill's full content, or load a specific reference document from it.

        **Without reference_title** (activate mode):
        Loads and returns the skill's instructions, prompt_template, code status,
        parameters_schema, list of available reference titles, and a usage guidance
        string that tells you which tool to call next:
        - instruction skill → follow instructions directly, do NOT call use_skill.
        - code skill        → call use_skill to execute.
        - hybrid skill      → follow instructions, then call use_skill for the code.
        - prompt skill      → apply the prompt_template to the relevant data.

        Always call get_skill (without reference_title) before using a skill for
        the first time in a conversation to understand its content and guidance.

        **With reference_title** (reference mode):
        Loads a single reference document attached to the skill. Use the titles
        returned by the activate call to know which references are available.

        Args:
            name: Exact name of the skill to load.
            reference_title: If provided, load this specific reference document
                             instead of the full skill content.

        Returns:
            JSON with skill content and guidance (activate mode) or reference
            content (reference mode).
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
                UserSkillModel.name == name,
                UserSkillModel.is_active == True,
            ).first()

            if not skill:
                return json.dumps({"success": False, "message": f"No active skill named '{name}' found"})

            # Reference mode
            if reference_title:
                ref = db.query(SkillReferenceModel).filter(
                    SkillReferenceModel.skill_id == skill.id,
                    SkillReferenceModel.title == reference_title,
                ).first()
                if not ref:
                    return json.dumps({
                        "success": False,
                        "message": f"No reference titled '{reference_title}' found in skill '{name}'",
                    })
                return json.dumps({
                    "success": True,
                    "skill_name": name,
                    "reference_title": reference_title,
                    "content": ref.content,
                })

            # Activate mode
            ref_titles = (
                [r.title for r in sorted(skill.references, key=lambda r: r.sort_order)]
                if skill.references
                else []
            )

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
                "skill_name": name,
                "skill_type": skill_type,
                "instructions": skill.instructions,
                "prompt_template": skill.prompt_template,
                "has_code": bool(skill.code),
                "parameters_schema": skill.parameters_schema,
                "references": ref_titles,
                "guidance": guidance,
            })
        except Exception as exc:
            logger.error(f"get_skill failed for '{name}': {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Tool 3: use_skill
    # ------------------------------------------------------------------

    @tool
    async def use_skill(skill_name: str, params_json: str = "{}") -> str:
        """
        Execute a previously created skill. Call get_skill first to load the skill.

        For instruction-only skills, use get_skill and follow the instructions instead.

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
                    error_msg = result["error"]
                    if "not allowed" in error_msg or "Import" in error_msg:
                        from backend.agents.skills.executor import _ALLOWED_MODULES
                        return json.dumps({
                            "success": False,
                            "message": (
                                f"{error_msg}. Fix the skill code using "
                                f"manage_skill(action='update', skill_name='{skill_name}', code='...') "
                                f"with allowed modules only. Allowed: {', '.join(sorted(_ALLOWED_MODULES))}. "
                                f"Do NOT retry use_skill until the code is fixed."
                            ),
                        })
                    return json.dumps({"success": False, "message": error_msg})
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

    # ------------------------------------------------------------------
    # Tool 4: list_skills
    # ------------------------------------------------------------------

    @tool
    async def list_skills() -> str:
        """
        List all your active skills with their names, types, and descriptions.

        Returns:
            JSON with a "skills" array. Each entry includes name, description,
            skill_type, has_instructions, has_code, has_prompt_template,
            activation_hint, and parameters_schema.
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
                        "activation_hint": s.activation_hint,
                        "parameters_schema": s.parameters_schema,
                    }
                    for s in skills
                ],
            })
        except Exception as exc:
            logger.error(f"list_skills failed: {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Tool 5: handle_suggestion
    # ------------------------------------------------------------------

    @tool
    async def handle_suggestion(
        action: str,
        suggestion_id: str = "",
    ) -> str:
        """
        Check pending skill suggestions or accept / dismiss a specific one.

        Background analysis periodically detects repeated patterns in conversations
        and proposes candidate skills. Use this tool to surface those proposals and
        act on them with the user's guidance.

        **Workflow:**
        1. Call with action="check" at the start of a conversation to see if any
           suggestions are waiting. Up to 3 are returned, ordered by confidence.
        2. Present the suggestions to the user and ask whether to accept or dismiss.
        3. Call with action="accept" or action="dismiss" using the suggestion's id.

        **action = "check"**
        Returns up to 3 pending suggestions. Each entry contains:
          id, suggested_name, suggested_description, suggested_skill_type,
          pattern_summary, confidence

        **action = "accept"**
        Creates a new skill from the suggestion and marks it accepted.
        Required: suggestion_id

        **action = "dismiss"**
        Marks the suggestion as dismissed without creating a skill.
        Required: suggestion_id

        Args:
            action: "check", "accept", or "dismiss".
            suggestion_id: ID of the suggestion to act on (required for
                           accept / dismiss; ignored for check).

        Returns:
            JSON with "success" bool and either a "suggestions" list (check) or
            a "message" string (accept / dismiss / errors).
        """
        if action == "check":
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
                logger.error(f"handle_suggestion(check) failed: {exc}")
                return json.dumps({"success": False, "message": str(exc)})
            finally:
                db.close()

        elif action in ("accept", "dismiss"):
            if not suggestion_id:
                return json.dumps({
                    "success": False,
                    "message": f"suggestion_id is required for action='{action}'",
                })

            from backend.models.skill_suggestion import SkillSuggestion as SkillSuggestionModel
            from backend.models.user_skill import UserSkill as UserSkillModel
            import uuid

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
                logger.error(f"handle_suggestion({action}) failed: {exc}")
                return json.dumps({"success": False, "message": str(exc)})
            finally:
                db.close()

        else:
            return json.dumps({
                "success": False,
                "message": f"Unknown action '{action}'. Must be 'check', 'accept', or 'dismiss'.",
            })

    return [manage_skill, get_skill, use_skill, list_skills, handle_suggestion]


# ---------------------------------------------------------------------------
# Internal helpers (not exposed as tools)
# ---------------------------------------------------------------------------


def _validate_skill_imports(code: str) -> "Optional[str]":
    """Return an error message if *code* uses disallowed imports, else None."""
    import ast
    from backend.agents.skills.executor import _ALLOWED_MODULES

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None  # syntax errors are caught later at execution time

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in _ALLOWED_MODULES:
                    return (
                        f"Module '{alias.name}' is not allowed in skill code. "
                        f"Allowed modules: {', '.join(sorted(_ALLOWED_MODULES))}"
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top not in _ALLOWED_MODULES:
                return (
                    f"Module '{node.module}' is not allowed in skill code. "
                    f"Allowed modules: {', '.join(sorted(_ALLOWED_MODULES))}"
                )
    return None

async def _create_skill(
    context: AgentContext,
    db_session_factory: Callable,
    name: str,
    description: str,
    instructions: str,
    prompt_template: str,
    code: str,
    parameters_schema: str,
    secrets: str,
    activation_hint: str,
    references: str,
) -> str:
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

        # Validate imports in code before saving
        if code:
            import_err = _validate_skill_imports(code)
            if import_err:
                return json.dumps({"success": False, "message": import_err})

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
        logger.error(f"manage_skill(create) failed: {exc}")
        return json.dumps({"success": False, "message": str(exc)})
    finally:
        db.close()


async def _update_skill(
    context: AgentContext,
    db_session_factory: Callable,
    skill_name: str,
    description: str,
    instructions: str,
    prompt_template: str,
    code: str,
    parameters_schema: str,
    activation_hint: str,
    add_references: str,
    remove_reference_titles: str,
) -> str:
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

        # Validate imports in new code before saving
        if code:
            import_err = _validate_skill_imports(code)
            if import_err:
                return json.dumps({"success": False, "message": import_err})

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
        logger.error(f"manage_skill(update) failed: {exc}")
        return json.dumps({"success": False, "message": str(exc)})
    finally:
        db.close()


async def _delete_skill(
    context: AgentContext,
    db_session_factory: Callable,
    skill_name: str,
) -> str:
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
        logger.error(f"manage_skill(delete) failed: {exc}")
        return json.dumps({"success": False, "message": str(exc)})
    finally:
        db.close()
