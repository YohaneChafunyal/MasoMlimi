import os, tempfile
_d = tempfile.mkdtemp(prefix="mm_test_")
os.environ.update(MASOMLIMI_API_KEY="test-key-123", MASOMLIMI_DATA_DIR=_d, MASOMLIMI_PRIVACY_SALT="t", MASOMLIMI_DATA_KEY="unit-test-data-key")
