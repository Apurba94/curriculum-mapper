"""Start the app: python -m curriculum_mapper [data.db] [--port 8029]"""
import sys

from .fieldkit import main_cli
from .web import create_app

sys.exit(main_cli(create_app, "curriculum.db", 8029, sys.argv))
