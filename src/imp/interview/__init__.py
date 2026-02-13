"""Imp interview — spec schema, validation, and portable interview skills.

Architecture (conversation 021): Imp owns the schema and validation, not the
conversation. The interview skill is pluggable — Imp ships a default, users
can bring their own. The contract is the output schema.

Public API:
    Models: InterviewSpec, SpecComponent, StakeholderProfile, InterviewMetadata,
            CompletenessResult, SpecGap, GapSeverity, InterviewMode
    Validation: validate_spec, validate_spec_file
    Skills: get_default_skill_path, get_domain_library_path, list_available_domains
"""

from imp.interview.models import (
    CompletenessResult,
    GapSeverity,
    InterviewMetadata,
    InterviewMode,
    InterviewSpec,
    SpecComponent,
    SpecGap,
    StakeholderProfile,
)
from imp.interview.skills import (
    get_default_skill_path,
    get_domain_library_path,
    list_available_domains,
)
from imp.interview.validator import validate_spec, validate_spec_file

__all__ = [
    "CompletenessResult",
    "GapSeverity",
    "InterviewMetadata",
    "InterviewMode",
    "InterviewSpec",
    "SpecComponent",
    "SpecGap",
    "StakeholderProfile",
    "get_default_skill_path",
    "get_domain_library_path",
    "list_available_domains",
    "validate_spec",
    "validate_spec_file",
]
