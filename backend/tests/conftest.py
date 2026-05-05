"""Pytest configuration and fixtures for backend tests."""
import sys
from types import ModuleType
from unittest.mock import MagicMock

# Mock external dependencies that may not be installed in test environment
# This should be done before any imports of backend modules

def _create_module_hierarchy(module_name, submodules=None):
    """Create a module hierarchy for mocking."""
    parts = module_name.split('.')
    parent = None
    for i, part in enumerate(parts):
        full_name = '.'.join(parts[:i+1])
        if full_name not in sys.modules:
            mod = ModuleType(full_name)
            sys.modules[full_name] = mod
            if parent:
                setattr(parent, part, mod)
            parent = mod
        else:
            parent = sys.modules[full_name]

    if submodules:
        for sub in submodules:
            sub_parts = sub.split('.')
            for j, part in enumerate(sub_parts):
                full_name = f"{module_name}.{'.'.join(sub_parts[:j+1])}"
                if full_name not in sys.modules:
                    mod = ModuleType(full_name)
                    sys.modules[full_name] = mod
                    if j > 0:
                        parent_name = f"{module_name}.{'.'.join(sub_parts[:j])}"
                        setattr(sys.modules[parent_name], part, mod)
                    else:
                        setattr(sys.modules[module_name], part, mod)

    return sys.modules[module_name]

# Create module hierarchies for external dependencies
_create_module_hierarchy('celery', ['schedules', 'result'])
_create_module_hierarchy('dlt', [])
_create_module_hierarchy('anthropic', [])
_create_module_hierarchy('qdrant_client', ['models'])
_create_module_hierarchy('langgraph', ['graph', 'checkpoint.memory'])
_create_module_hierarchy('openai', [])
_create_module_hierarchy('redis', ['asyncio'])
_create_module_hierarchy('tiktoken', [])
_create_module_hierarchy('croniter', [])
_create_module_hierarchy('sqlalchemy', ['orm', 'pool', 'dialects', 'dialects.postgresql'])
_create_module_hierarchy('fastapi', ['security'])

# Add common mock attributes
sys.modules['celery'].Celery = MagicMock()
sys.modules['celery'].Task = MagicMock()
sys.modules['celery.schedules'].crontab = MagicMock()
sys.modules['celery.result'].AsyncResult = MagicMock()

sys.modules['dlt'].pipeline = MagicMock()
sys.modules['dlt'].run = MagicMock()

sys.modules['sqlalchemy.orm'].Session = MagicMock()
sys.modules['sqlalchemy.orm'].sessionmaker = MagicMock()
sys.modules['sqlalchemy.orm'].relationship = MagicMock()
sys.modules['sqlalchemy.pool'].NullPool = MagicMock()
sys.modules['sqlalchemy'].create_engine = MagicMock()
sys.modules['sqlalchemy'].Column = MagicMock()
sys.modules['sqlalchemy'].String = MagicMock()
sys.modules['sqlalchemy'].ForeignKey = MagicMock()
sys.modules['sqlalchemy'].JSON = MagicMock()
sys.modules['sqlalchemy'].Text = MagicMock()
sys.modules['sqlalchemy'].Integer = MagicMock()
sys.modules['sqlalchemy'].Boolean = MagicMock()
sys.modules['sqlalchemy'].DateTime = MagicMock()

sys.modules['tiktoken'].Encoding = MagicMock()
sys.modules['tiktoken'].get_encoding = MagicMock()

# croniter mock - return a mock instance with get_next method
def _croniter_mock(cron_expr, base_time):
    """Return a mock croniter that advances time."""
    mock_cron = MagicMock()
    # get_next should return a datetime after the base_time
    from datetime import timedelta
    mock_cron.get_next = MagicMock(return_value=base_time + timedelta(hours=1))
    return mock_cron

sys.modules['croniter'].croniter = _croniter_mock

sys.modules['redis'].from_url = MagicMock()
sys.modules['redis'].Redis = MagicMock()

sys.modules['openai'].AsyncOpenAI = MagicMock()
sys.modules['openai'].RateLimitError = Exception
sys.modules['openai'].APIError = Exception

sys.modules['qdrant_client'].QdrantClient = MagicMock()
sys.modules['qdrant_client'].QdrantClient.from_url = MagicMock()
sys.modules['qdrant_client.models'].Distance = MagicMock()
sys.modules['qdrant_client.models'].VectorParams = MagicMock()
sys.modules['qdrant_client.models'].PointStruct = MagicMock()
sys.modules['qdrant_client.models'].Filter = MagicMock()
sys.modules['qdrant_client.models'].FieldCondition = MagicMock()
sys.modules['qdrant_client.models'].MatchValue = MagicMock()
