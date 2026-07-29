class GoBugMinerError(Exception):
    """Base expected failure."""


class ConfigurationError(GoBugMinerError):
    pass


class DependencyError(GoBugMinerError):
    pass


class GitHubError(GoBugMinerError):
    pass


class RepositoryError(GoBugMinerError):
    pass


class ExtractionError(GoBugMinerError):
    pass


class ValidationError(GoBugMinerError):
    pass
