"""Root pytest configuration for all test directories."""


def pytest_addoption(parser):
    """Register custom pytest options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires Neo4j, PostgreSQL)",
    )
