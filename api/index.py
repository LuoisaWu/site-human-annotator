import sys
import os

# Add annotation_platform to path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'annotation_platform'))

from app import app