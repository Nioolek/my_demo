import os
import pytest

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
