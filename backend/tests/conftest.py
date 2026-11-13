import os

# The backend refuses to start without a signing secret; tests use a fixed, test-only one.
os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-0123456789")
