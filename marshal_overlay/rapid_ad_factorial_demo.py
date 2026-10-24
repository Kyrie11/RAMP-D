"""MARSHAL scenario entrypoint for RAPID-AD.

The RAPID-AD project root must be on PYTHONPATH so this module can import
rapid_ad.scenario. The custom runner does not alter MARSHAL's scenario registry.
"""
from rapid_ad.scenario import run

__all__ = ["run"]
