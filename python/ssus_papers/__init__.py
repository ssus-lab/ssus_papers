"""Presentation helpers for SSUS papers, beside the Quarto formats.

A project's formatting script reads the analysis outputs, formats the
numbers, and hands them to `Table`, which writes one Quarto include serving
every format the paper renders to. `python -m ssus_papers.submit` freezes a
journal submission: the upload bundle and a snapshot of the paper's source.
"""

from .tables import Table

__all__ = ["Table"]
__version__ = "0.0.8"
