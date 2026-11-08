"""Presentation helpers for SSUS papers, beside the Quarto formats.

A project's formatting script reads the analysis outputs, formats the
numbers, and hands them to `Table`, which writes one Quarto include serving
every format the paper renders to. `python -m ssus_papers.submit` stages a
journal's upload bundle from the rendered blind manuscript and title page.
"""

from .tables import Table

__all__ = ["Table"]
__version__ = "0.0.7"
