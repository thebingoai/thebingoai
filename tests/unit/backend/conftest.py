# Import UserSkill to satisfy SkillReference's relationship() mapper resolution.
# UserSkill uses JSONB (Postgres-only) so we don't create its table in SQLite tests,
# but it must be imported so SQLAlchemy can resolve the 'UserSkill' string reference.
import backend.models.user_skill  # noqa: F401
