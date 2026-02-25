import pytest
import os
import shutil

# Set environment variable BEFORE importing app from main
os.environ["GARRAT_GAMES_DIR"] = "test_games_tmp"

from fastapi.testclient import TestClient
from main import app

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    test_dir = "test_games_tmp"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    
    # Ensure narrat_syntax.md exists for tests
    if not os.path.exists("narrat_syntax.md"):
        with open("narrat_syntax.md", "w") as f:
            f.write("# Test Syntax")
            
    yield
    
    # Cleanup after all tests
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
