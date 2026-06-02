"""Session debug logging (agent instrumentation)."""

import json
import time
from pathlib import Path

_DEBUG_LOG_PATH = Path('/Users/joel/Github/Vessel/.cursor/Logs/debug-c7d5e0.log')
_DEBUG_SESSION_ID = 'c7d5e0'


def agent_debug_log(
    *,
    location: str,
    message: str,
    data: dict[str, object],
    hypothesis_id: str,
    run_id: str = 'pre-fix',
) -> None:
    """Append one NDJSON debug line for the active agent session."""
    # region agent log
    payload = {
        'sessionId': _DEBUG_SESSION_ID,
        'location': location,
        'message': message,
        'data': data,
        'timestamp': int(time.time() * 1000),
        'hypothesisId': hypothesis_id,
        'runId': run_id,
    }
    try:
        with _DEBUG_LOG_PATH.open('a', encoding='utf-8') as log_file:
            log_file.write(json.dumps(payload) + '\n')
    except OSError:
        pass
    # endregion
