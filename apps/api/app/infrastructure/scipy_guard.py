"""Process-wide guard for native SciPy optimizers that are unsafe under Windows threads."""

import threading

SCIPY_OPTIMIZATION_LOCK = threading.Lock()
