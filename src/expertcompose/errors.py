"""Public product errors with actionable messages."""


class ExpertComposeError(Exception):
    """Base class for expected product failures."""


class ProjectNotFoundError(ExpertComposeError):
    """Raised when a requested project does not exist."""


class InvalidTransitionError(ExpertComposeError):
    """Raised when governance state would move through an illegal edge."""


class SourceImportError(ExpertComposeError):
    """Raised when a source cannot be normalized safely."""


class SynthesisError(ExpertComposeError):
    """Raised when a synthesis provider returns an invalid result."""


class PublicationBlockedError(ExpertComposeError):
    """Raised when release gates do not permit publication."""
