import sys
import os

# Add the project root to sys.path so app and its local modules can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
