"""Keep the clean trust-boundary stack inside its structural budgets."""

import ast

from conformance import rewrite_architecture_check
from conformance.rewrite_architecture_check import main


def test_rewrite_architecture_budgets():
    assert main() == 0


def test_runtime_config_from_env_is_the_only_environment_reader():
    source = """
import os as environment
class RuntimeConfig:
    @classmethod
    def from_env(cls):
        return environment.environ["SETTING"]
"""

    assert rewrite_architecture_check._environment_reads(
        ast.parse(source)
    ) == []
