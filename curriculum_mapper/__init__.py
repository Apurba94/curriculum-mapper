"""Curriculum Mapper: check that competencies, lessons and assessments line up."""
from . import core
from .web import create_app

__all__ = ["core", "create_app"]
