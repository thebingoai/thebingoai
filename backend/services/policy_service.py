"""
PolicyService — governance enforcement for team tool and connection policies.

Provides methods to query team-level permissions and validate agent configurations
against the current (runtime) team whitelist.
"""
from typing import List, Tuple
from sqlalchemy.orm import Session
from backend.models.team_tool_policy import TeamToolPolicy
from backend.models.team_connection_policy import TeamConnectionPolicy
from backend.models.team_membership import TeamMembership
import logging

logger = logging.getLogger(__name__)


class PolicyService:
    """Static-method service for team policy queries."""

    @staticmethod
    def get_team_allowed_tools(db: Session, team_id: str) -> List[str]:
        """Return list of tool_keys enabled for this team."""
        rows = db.query(TeamToolPolicy).filter(
            TeamToolPolicy.team_id == team_id,
            TeamToolPolicy.is_enabled == True,
        ).all()
        return [r.tool_key for r in rows]

    @staticmethod
    def get_team_allowed_connections(db: Session, team_id: str) -> List[int]:
        """Return list of connection_ids enabled for this team."""
        rows = db.query(TeamConnectionPolicy).filter(
            TeamConnectionPolicy.team_id == team_id,
            TeamConnectionPolicy.is_enabled == True,
        ).all()
        return [r.connection_id for r in rows]

    @staticmethod
    def validate_agent_tools(
        db: Session,
        team_id: str,
        requested_tools: List[str],
    ) -> Tuple[bool, List[str]]:
        """
        Check that all requested_tools are within the team's current whitelist.

        Returns:
            (is_valid, violations)  — violations is an empty list when valid.
        """
        allowed = set(PolicyService.get_team_allowed_tools(db, team_id))
        violations = [t for t in requested_tools if t not in allowed]
        return (len(violations) == 0, violations)

    @staticmethod
    def validate_agent_connections(
        db: Session,
        team_id: str,
        requested_connection_ids: List[int],
    ) -> Tuple[bool, List[int]]:
        """
        Check that all requested connection_ids are within the team's current whitelist.

        Returns:
            (is_valid, violations)
        """
        allowed = set(PolicyService.get_team_allowed_connections(db, team_id))
        violations = [c for c in requested_connection_ids if c not in allowed]
        return (len(violations) == 0, violations)

    @staticmethod
    def get_user_primary_team(db: Session, user_id: str) -> str | None:
        """Return the team_id for the user's first team membership (or None)."""
        membership = db.query(TeamMembership).filter(
            TeamMembership.user_id == user_id
        ).first()
        return membership.team_id if membership else None
