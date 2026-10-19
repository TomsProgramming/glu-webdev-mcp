import os
import tempfile

# Tests gebruiken een lege, tijdelijke cache en raken het netwerk niet aan.
os.environ["GLU_CACHE_DIR"] = tempfile.mkdtemp(prefix="glu-webdev-mcp-test-")
