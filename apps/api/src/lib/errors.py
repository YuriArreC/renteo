"""Typed errors for the tax domain.

Each error maps to an explicit HTTP status in the global exception handler
(see fastapi-supabase-patterns skill).
"""


class TaxError(Exception):
    """Base class for tax-domain errors."""


class IneligibleForRegime(TaxError):
    """Contributor does not meet the objective requirements of the regime."""


class RedFlagBlocked(TaxError):
    """Configuration triggers a red-flag pattern from the blacklist."""


class MissingTaxYearParams(TaxError):
    """No parameters published for the requested tax_year."""


class MissingRuleError(TaxError):
    """No published rule_set covers the requested (domain, key, tax_year)."""


class SiiUnavailable(TaxError):
    """SII provider is unreachable or returned a transient failure."""


class SiiAuthError(TaxError):
    """SII provider rejected the credentials (token or certificate)."""


class SiiTimeout(TaxError):
    """SII provider did not respond within the configured budget."""


class CertificateError(TaxError):
    """Digital certificate is invalid, expired, or cannot be decrypted."""


class ConsentMissing(TaxError):
    """Required user consent has not been granted or has been revoked."""


class InvalidRuleError(TaxError):
    """Declarative rule is malformed (unknown clause shape, bad value)."""


class UnsupportedOperatorError(TaxError):
    """Rule uses an operator outside the supported set (skill 11)."""
