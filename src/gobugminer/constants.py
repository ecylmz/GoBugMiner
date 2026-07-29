from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 2
    DEPENDENCY = 3
    GITHUB = 4
    REPOSITORY = 5
    EXTRACTION = 6
    VALIDATION = 7
    PARTIAL = 8
    INTERNAL = 10


LEVELS = ("commit", "file", "method")
STAGES = (
    "environment_preflight",
    "configuration_validation",
    "github_authentication",
    "rate_limit",
    "pull_request_discovery",
    "pull_request_resolution",
    "fix_commit_resolution",
    "repository_acquisition",
    "bic_extraction",
    "commit_extraction",
    "file_extraction",
    "method_extraction",
    "relation_assembly",
    "output_writing",
    "provenance_capture",
    "validation",
    "final_summary",
)
