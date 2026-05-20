class ATSBaseError(Exception):
    """Root exception for all ATS system errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AgentError(ATSBaseError):
    """Raised when an agent fails to complete its analysis."""

    def __init__(self, agent_name: str, message: str, details: dict | None = None) -> None:
        super().__init__(message, details)
        self.agent_name = agent_name


class ContractValidationError(ATSBaseError):
    """Raised when agent output does not satisfy the AgentOutput contract."""


class ConfigurationError(ATSBaseError):
    """Raised when required configuration is missing or invalid."""


class StorageError(ATSBaseError):
    """Raised when a database or vector-store operation fails."""


class IngestionError(ATSBaseError):
    """Raised when the data ingestion pipeline encounters an unrecoverable error."""


class RAGError(ATSBaseError):
    """Raised when retrieval-augmented generation lookup fails."""


class MCPError(ATSBaseError):
    """Raised when an MCP tool call fails or times out."""
