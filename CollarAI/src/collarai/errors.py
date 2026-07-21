class CollarAIError(RuntimeError):
    """Base error for expected browser-service failures."""


class AuthenticationRequired(CollarAIError):
    """A human must finish login, MFA, or a CAPTCHA in the browser session."""


class ConfigurationRequired(CollarAIError):
    """The target site's adapter has not been configured yet."""


class PolicyViolation(CollarAIError):
    """A request or extracted result violated the configured policy."""


class WorkflowError(CollarAIError):
    """A deterministic workflow step and its recovery both failed."""


class BrowserConnectionLost(WorkflowError):
    """The local browser-control connection closed and may be safely recreated."""
