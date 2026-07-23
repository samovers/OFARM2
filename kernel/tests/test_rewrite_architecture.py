"""Keep the clean trust-boundary stack inside its structural budgets."""

from conformance.rewrite_architecture_check import main


def test_rewrite_architecture_budgets():
    assert main() == 0
