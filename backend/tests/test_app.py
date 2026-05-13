import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import main


def test_app_has_title():
    assert hasattr(main, "app")
    assert main.app.title.startswith("MediScan Gateway")
