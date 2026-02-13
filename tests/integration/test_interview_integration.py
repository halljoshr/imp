"""Integration tests for interview layer - full end-to-end workflows.

These tests cover:
- Full validate workflow (spec dict → JSON → validate → CompletenessResult)
- Full import workflow (spec → JSON → import → re-validate)
- Round-trip serialization (spec → JSON → spec)
- Gap analysis workflow (partial spec → validate → fill gaps → re-validate)
- CLI integration via CliRunner (validate and import commands)
- Large spec handling
- Minimal complete spec
- JSON format output
- Public API imports
"""

import json
from datetime import date
from pathlib import Path

import pytest

from imp.interview import (
    CompletenessResult,
    GapSeverity,
    InterviewMetadata,
    InterviewMode,
    InterviewSpec,
    SpecComponent,
    SpecGap,
    StakeholderProfile,
    validate_spec,
    validate_spec_file,
)
from imp.interview.cli import import_command, validate_command

# Fixtures for reuse


@pytest.fixture
def complete_spec_dict() -> dict:
    """Complete spec dictionary for testing."""
    return {
        "name": "Test Auth System",
        "problem_statement": (
            "Users need secure authentication with automatic token refresh "
            "to prevent data loss during long sessions"
        ),
        "system_overview": "OAuth-based auth with token management",
        "components": [
            {
                "name": "Auth Provider",
                "purpose": "Handle OAuth login flow",
                "inputs": ["user credentials", "OAuth config"],
                "outputs": ["access token", "refresh token", "user profile"],
                "constraints": ["must support Google OAuth"],
                "edge_cases": ["token expiry during form submission"],
                "success_criteria": ["login completes within 3 seconds"],
            },
            {
                "name": "Token Manager",
                "purpose": "Automatic background token refresh",
                "inputs": ["expiring access token", "refresh token"],
                "outputs": ["new access token"],
                "constraints": ["must refresh before expiry"],
                "edge_cases": ["refresh token revoked by provider"],
                "success_criteria": ["no user-visible session interruptions"],
            },
        ],
        "success_criteria": ["end-to-end auth works", "no data loss on token expiry"],
        "out_of_scope": ["multi-provider OAuth", "passwordless auth"],
        "constraints": ["HTTPS required", "GDPR compliant"],
        "stakeholder_profile": {
            "working_style": "terminal-first developer",
            "values": ["security", "reliability"],
            "pain_points": ["random logouts causing data loss"],
            "priorities": ["never lose user work"],
            "technical_preferences": ["Python", "FastAPI"],
        },
        "metadata": {
            "interview_date": "2026-02-13",
            "mode": "direct",
            "completeness_score": 95,
            "domain": "software-requirements",
            "question_count": 18,
        },
    }


@pytest.fixture
def partial_spec_dict() -> dict:
    """Partial/incomplete spec dictionary for testing."""
    return {
        "name": "Incomplete Feature",
        "problem_statement": "Need to add a search feature",
        "components": [
            {
                "name": "Search Engine",
                "purpose": "Full-text search across content",
            }
        ],
    }


class TestFullValidateWorkflow:
    """Integration tests for full validate workflow end-to-end."""

    def test_validate_complete_spec_from_dict(self, complete_spec_dict: dict) -> None:
        """Complete spec dict → InterviewSpec → validate → high score."""
        spec = InterviewSpec.model_validate(complete_spec_dict)
        result = validate_spec(spec)

        assert result.score >= 80
        assert result.is_complete
        assert len(result.critical_gaps) == 0

    def test_validate_complete_spec_from_file(
        self, tmp_path: Path, complete_spec_dict: dict
    ) -> None:
        """Complete spec → JSON file → validate_spec_file → high score."""
        spec_file = tmp_path / "complete.json"
        spec_file.write_text(json.dumps(complete_spec_dict, indent=2))

        result = validate_spec_file(spec_file)

        assert result.score >= 80
        assert result.is_complete
        assert isinstance(result, CompletenessResult)

    def test_validate_partial_spec_from_dict(self, partial_spec_dict: dict) -> None:
        """Partial spec dict → InterviewSpec → validate → low score with gaps."""
        spec = InterviewSpec.model_validate(partial_spec_dict)
        result = validate_spec(spec)

        assert result.score < 80
        assert not result.is_complete
        assert len(result.gaps) > 0
        assert len(result.critical_gaps) > 0

    def test_validate_partial_spec_from_file(
        self, tmp_path: Path, partial_spec_dict: dict
    ) -> None:
        """Partial spec → JSON file → validate_spec_file → gaps identified."""
        spec_file = tmp_path / "partial.json"
        spec_file.write_text(json.dumps(partial_spec_dict, indent=2))

        result = validate_spec_file(spec_file)

        assert result.score < 80
        assert not result.is_complete
        assert result.gap_count > 0


class TestFullImportWorkflow:
    """Integration tests for full import workflow end-to-end."""

    def test_import_complete_spec_end_to_end(
        self, tmp_path: Path, complete_spec_dict: dict
    ) -> None:
        """Complete spec → JSON file → import_command → verify imported file exists."""
        # Write spec to temp file
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(complete_spec_dict, indent=2))

        # Import to output dir
        output_dir = tmp_path / "output"
        exit_code = import_command(spec_file, output_dir=output_dir, format="json")

        # Verify success
        assert exit_code == 0
        imported_file = output_dir / "spec.json"
        assert imported_file.exists()

        # Re-validate imported file
        result = validate_spec_file(imported_file)
        assert result.is_complete

    def test_import_incomplete_spec_fails(self, tmp_path: Path, partial_spec_dict: dict) -> None:
        """Partial spec → JSON file → import_command → fails with exit code 1."""
        spec_file = tmp_path / "partial.json"
        spec_file.write_text(json.dumps(partial_spec_dict, indent=2))

        exit_code = import_command(spec_file, format="json")

        assert exit_code == 1

    def test_import_to_default_location(
        self, tmp_path: Path, complete_spec_dict: dict, monkeypatch
    ) -> None:
        """Import without output_dir → defaults to .imp/specs/."""
        # Change CWD to tmp_path so .imp/specs/ is created there
        monkeypatch.chdir(tmp_path)

        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(complete_spec_dict, indent=2))

        exit_code = import_command(spec_file, format="json")

        assert exit_code == 0
        default_location = tmp_path / ".imp" / "specs" / "spec.json"
        assert default_location.exists()

    def test_import_creates_output_dir_if_missing(
        self, tmp_path: Path, complete_spec_dict: dict
    ) -> None:
        """Import to non-existent dir → creates directory."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(complete_spec_dict, indent=2))

        output_dir = tmp_path / "new" / "nested" / "dir"
        assert not output_dir.exists()

        exit_code = import_command(spec_file, output_dir=output_dir, format="json")

        assert exit_code == 0
        assert output_dir.exists()
        assert (output_dir / "spec.json").exists()


class TestRoundTripSerialization:
    """Integration tests for round-trip serialization."""

    def test_spec_round_trip_same_score(self, complete_spec_dict: dict) -> None:
        """InterviewSpec → validate → model_dump_json → parse → validate → same score."""
        # First validation
        spec1 = InterviewSpec.model_validate(complete_spec_dict)
        result1 = validate_spec(spec1)

        # Serialize to JSON
        json_str = spec1.model_dump_json(indent=2)

        # Deserialize back to spec
        spec2 = InterviewSpec.model_validate_json(json_str)
        result2 = validate_spec(spec2)

        # Verify same score both times
        assert result1.score == result2.score
        assert result1.is_complete == result2.is_complete
        assert len(result1.gaps) == len(result2.gaps)

    def test_completeness_result_round_trip(self, partial_spec_dict: dict) -> None:
        """CompletenessResult → model_dump_json → parse → verify structure."""
        spec = InterviewSpec.model_validate(partial_spec_dict)
        result = validate_spec(spec)

        # Serialize
        json_str = result.model_dump_json(indent=2)

        # Deserialize
        data = json.loads(json_str)
        restored = CompletenessResult.model_validate(data)

        # Verify same data
        assert restored.score == result.score
        assert restored.gap_count == result.gap_count
        assert len(restored.critical_gaps) == len(result.critical_gaps)

    def test_spec_with_all_fields_round_trip(self, complete_spec_dict: dict) -> None:
        """Spec with all fields populated → round trip → no data loss."""
        spec1 = InterviewSpec.model_validate(complete_spec_dict)

        # Serialize
        json_data = spec1.model_dump()

        # Deserialize
        spec2 = InterviewSpec.model_validate(json_data)

        # Verify all fields preserved
        assert spec2.name == spec1.name
        assert spec2.problem_statement == spec1.problem_statement
        assert len(spec2.components) == len(spec1.components)
        assert spec2.components[0].inputs == spec1.components[0].inputs
        assert spec2.stakeholder_profile is not None
        assert spec2.metadata is not None


class TestGapAnalysisWorkflow:
    """Integration tests for gap analysis workflow."""

    def test_gap_analysis_fill_and_revalidate(self, partial_spec_dict: dict) -> None:
        """Partial spec → validate → identify gaps → fill → re-validate → higher score."""
        # Initial validation
        spec1 = InterviewSpec.model_validate(partial_spec_dict)
        result1 = validate_spec(spec1)

        initial_score = result1.score
        assert initial_score < 80
        assert len(result1.critical_gaps) > 0

        # Programmatically fill gaps
        filled_dict = partial_spec_dict.copy()
        filled_dict["components"][0]["inputs"] = ["search query", "filter options"]
        filled_dict["components"][0]["outputs"] = ["search results", "result count"]
        filled_dict["components"][0]["edge_cases"] = [
            "empty search query",
            "no results found",
        ]
        filled_dict["components"][0]["success_criteria"] = ["search returns within 500ms"]
        filled_dict["success_criteria"] = ["search works for all content types"]
        filled_dict["constraints"] = ["must handle 10k+ documents"]

        # Re-validate
        spec2 = InterviewSpec.model_validate(filled_dict)
        result2 = validate_spec(spec2)

        # Verify improvement
        assert result2.score > initial_score
        assert len(result2.critical_gaps) < len(result1.critical_gaps)

    def test_gap_analysis_identifies_critical_gaps(self, partial_spec_dict: dict) -> None:
        """Partial spec → validate → verify critical gaps have suggested questions."""
        spec = InterviewSpec.model_validate(partial_spec_dict)
        result = validate_spec(spec)

        critical_gaps = result.critical_gaps
        assert len(critical_gaps) > 0

        # Verify each critical gap has suggested questions
        for gap in critical_gaps:
            assert len(gap.suggested_questions) > 0
            assert isinstance(gap, SpecGap)
            assert gap.severity == GapSeverity.CRITICAL

    def test_gap_analysis_minimal_to_complete(self) -> None:
        """Minimal spec → validate → fill all gaps → reach completeness threshold."""
        minimal = {
            "name": "Feature",
        }

        spec1 = InterviewSpec.model_validate(minimal)
        result1 = validate_spec(spec1)

        assert result1.score < 80

        # Fill to make complete
        complete = {
            "name": "Feature",
            "problem_statement": "Users need a way to export their data for compliance",
            "components": [
                {
                    "name": "Export Service",
                    "purpose": "Export user data to CSV",
                    "inputs": ["user ID", "date range"],
                    "outputs": ["CSV file", "export log"],
                    "edge_cases": ["no data in range"],
                    "success_criteria": ["export completes within 10 seconds"],
                }
            ],
            "success_criteria": ["users can export all their data"],
            "out_of_scope": ["real-time streaming"],
            "constraints": ["must be GDPR compliant"],
            "stakeholder_profile": {
                "working_style": "web-based admin",
                "values": ["compliance"],
                "pain_points": ["manual export requests"],
                "priorities": ["automation"],
                "technical_preferences": ["Python"],
            },
        }

        spec2 = InterviewSpec.model_validate(complete)
        result2 = validate_spec(spec2)

        assert result2.score >= 80
        assert result2.is_complete


class TestCLIIntegration:
    """Integration tests for CLI commands via CliRunner."""

    def test_cli_validate_complete_spec(self, tmp_path: Path, complete_spec_dict: dict) -> None:
        """CLI validate command → complete spec → exit code 0."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(complete_spec_dict, indent=2))

        exit_code = validate_command(spec_file, format="json")

        assert exit_code == 0

    def test_cli_validate_incomplete_spec(self, tmp_path: Path, partial_spec_dict: dict) -> None:
        """CLI validate command → incomplete spec → exit code 1."""
        spec_file = tmp_path / "partial.json"
        spec_file.write_text(json.dumps(partial_spec_dict, indent=2))

        exit_code = validate_command(spec_file, format="json")

        assert exit_code == 1

    def test_cli_validate_missing_file(self, tmp_path: Path) -> None:
        """CLI validate command → missing file → exit code 1."""
        missing_file = tmp_path / "does_not_exist.json"

        exit_code = validate_command(missing_file, format="json")

        assert exit_code == 1

    def test_cli_validate_invalid_json(self, tmp_path: Path) -> None:
        """CLI validate command → invalid JSON → exit code 1."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json")

        exit_code = validate_command(bad_file, format="json")

        assert exit_code == 1

    def test_cli_import_complete_spec(self, tmp_path: Path, complete_spec_dict: dict) -> None:
        """CLI import command → complete spec → exit code 0, file imported."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(complete_spec_dict, indent=2))

        output_dir = tmp_path / "output"
        exit_code = import_command(spec_file, output_dir=output_dir, format="json")

        assert exit_code == 0
        assert (output_dir / "spec.json").exists()

    def test_cli_import_incomplete_spec(self, tmp_path: Path, partial_spec_dict: dict) -> None:
        """CLI import command → incomplete spec → exit code 1."""
        spec_file = tmp_path / "partial.json"
        spec_file.write_text(json.dumps(partial_spec_dict, indent=2))

        exit_code = import_command(spec_file, format="json")

        assert exit_code == 1


class TestLargeSpecHandling:
    """Integration tests for large spec handling."""

    def test_validate_large_spec_with_many_components(self) -> None:
        """Large spec with 10+ components → validate → handles correctly."""
        large_spec_dict = {
            "name": "Large System",
            "problem_statement": "Build a comprehensive e-commerce platform with all features",
            "components": [
                {
                    "name": f"Component {i}",
                    "purpose": f"Handle feature {i}",
                    "inputs": [f"input_{i}_1", f"input_{i}_2"],
                    "outputs": [f"output_{i}_1"],
                    "edge_cases": [f"edge case {i}"],
                    "success_criteria": [f"component {i} works"],
                }
                for i in range(12)
            ],
            "success_criteria": ["entire system works end-to-end"],
            "constraints": ["scalable to 1M users"],
        }

        spec = InterviewSpec.model_validate(large_spec_dict)
        result = validate_spec(spec)

        # Verify it handles large specs correctly
        assert spec.component_count == 12
        assert result.score >= 70  # Should score reasonably well
        assert isinstance(result, CompletenessResult)

    def test_validate_large_spec_file(self, tmp_path: Path) -> None:
        """Large spec → JSON file → validate_spec_file → no errors."""
        large_spec = {
            "name": "Large Project",
            "problem_statement": "Need a comprehensive solution for enterprise data management",
            "components": [
                {
                    "name": f"Module {i}",
                    "purpose": f"Handle {i}",
                    "inputs": [f"in_{j}" for j in range(5)],
                    "outputs": [f"out_{j}" for j in range(3)],
                    "edge_cases": [f"edge_{j}" for j in range(4)],
                    "success_criteria": [f"criteria_{j}" for j in range(2)],
                }
                for i in range(15)
            ],
            "success_criteria": ["works", "scales", "secure"],
            "constraints": ["cloud-native", "HIPAA compliant"],
        }

        spec_file = tmp_path / "large.json"
        spec_file.write_text(json.dumps(large_spec, indent=2))

        result = validate_spec_file(spec_file)

        assert result.score >= 80
        assert result.is_complete


class TestMinimalCompleteSpec:
    """Integration tests for minimal complete spec."""

    def test_minimal_complete_spec_scores_80_plus(self) -> None:
        """Create smallest spec that scores >= 80 → verify is_complete."""
        # Minimal fields to reach 80+
        minimal_complete = {
            "name": "Minimal Feature",
            "problem_statement": (
                "Users need a simple way to reset their password when they forget it"
            ),
            "components": [
                {
                    "name": "Password Reset",
                    "purpose": "Send reset email with token",
                    "inputs": ["user email"],
                    "outputs": ["reset token", "email sent confirmation"],
                    "edge_cases": ["invalid email", "email not in system"],
                    "success_criteria": ["email arrives within 60 seconds"],
                }
            ],
            "success_criteria": ["users can reset password without support"],
            "out_of_scope": ["social login"],
            "constraints": ["token expires in 1 hour"],
            "stakeholder_profile": {
                "working_style": "admin panel",
                "values": ["simplicity"],
                "pain_points": ["too many support tickets"],
                "priorities": ["self-service"],
                "technical_preferences": ["Django"],
            },
        }

        spec = InterviewSpec.model_validate(minimal_complete)
        result = validate_spec(spec)

        assert result.score >= 80
        assert result.is_complete

    def test_minimal_complete_spec_no_critical_gaps(self) -> None:
        """Minimal complete spec → validate → no critical gaps."""
        minimal = {
            "name": "Feature",
            "problem_statement": "Need to notify users when their report is ready for download",
            "components": [
                {
                    "name": "Notification Service",
                    "purpose": "Send email when report completes",
                    "inputs": ["user ID", "report URL"],
                    "outputs": ["email sent status"],
                    "success_criteria": ["email sent within 1 minute"],
                }
            ],
            "success_criteria": ["users receive notifications"],
        }

        spec = InterviewSpec.model_validate(minimal)
        result = validate_spec(spec)

        # Should have no critical gaps
        assert len(result.critical_gaps) == 0


class TestJSONFormatOutput:
    """Integration tests for JSON format output."""

    def test_validate_json_format_output(
        self, tmp_path: Path, complete_spec_dict: dict, capsys
    ) -> None:
        """Validate with format='json' → parse output as JSON → verify structure."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(complete_spec_dict, indent=2))

        validate_command(spec_file, format="json")

        captured = capsys.readouterr()
        output_data = json.loads(captured.out)

        # Verify JSON structure matches CompletenessResult
        assert "score" in output_data
        assert "gaps" in output_data
        assert "suggestions" in output_data
        assert isinstance(output_data["score"], int)
        assert isinstance(output_data["gaps"], list)

    def test_validate_jsonl_format_output(
        self, tmp_path: Path, complete_spec_dict: dict, capsys
    ) -> None:
        """Validate with format='jsonl' → verify single-line JSON output."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(complete_spec_dict, indent=2))

        validate_command(spec_file, format="jsonl")

        captured = capsys.readouterr()
        # Should be single line
        assert captured.out.count("\n") == 1  # Just the trailing newline
        # Should be valid JSON
        data = json.loads(captured.out)
        assert "score" in data

    def test_import_json_format_output(
        self, tmp_path: Path, complete_spec_dict: dict, capsys
    ) -> None:
        """Import with format='json' → parse output → verify imported path."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(complete_spec_dict, indent=2))

        output_dir = tmp_path / "output"
        import_command(spec_file, output_dir=output_dir, format="json")

        captured = capsys.readouterr()
        output_data = json.loads(captured.out)

        assert output_data["imported"] is True
        assert "path" in output_data
        assert "score" in output_data


class TestPublicAPIImports:
    """Integration tests for public API imports from imp.interview."""

    def test_all_public_models_importable(self) -> None:
        """Verify all exports from imp.interview work."""
        # This test just verifies the imports work — actual imports done at module top
        assert InterviewSpec is not None
        assert SpecComponent is not None
        assert StakeholderProfile is not None
        assert InterviewMetadata is not None
        assert CompletenessResult is not None
        assert SpecGap is not None
        assert GapSeverity is not None
        assert InterviewMode is not None

    def test_validate_functions_importable(self) -> None:
        """Verify validation functions are exported."""
        assert validate_spec is not None
        assert validate_spec_file is not None

    def test_public_api_creates_valid_objects(self) -> None:
        """Use public API to create objects → verify they work."""
        component = SpecComponent(
            name="Test Component",
            purpose="Test purpose",
            inputs=["input1"],
            outputs=["output1"],
        )

        spec = InterviewSpec(
            name="Test Spec",
            problem_statement="Test problem",
            components=[component],
        )

        result = validate_spec(spec)

        assert isinstance(result, CompletenessResult)
        assert result.score > 0


class TestSpecValidationEdgeCases:
    """Integration tests for edge cases in spec validation."""

    def test_empty_spec_low_score(self) -> None:
        """Empty spec (only name) → validate → very low score."""
        empty = {"name": "Empty"}

        spec = InterviewSpec.model_validate(empty)
        result = validate_spec(spec)

        assert result.score < 30
        assert not result.is_complete
        assert len(result.critical_gaps) > 0

    def test_spec_with_empty_problem_statement(self) -> None:
        """Spec with empty string problem_statement → treated as missing."""
        spec_dict = {
            "name": "Test",
            "problem_statement": "",
        }

        spec = InterviewSpec.model_validate(spec_dict)
        result = validate_spec(spec)

        # Should flag missing problem statement
        problem_gaps = [g for g in result.gaps if g.field == "problem_statement"]
        assert len(problem_gaps) > 0

    def test_spec_with_components_but_no_details(self) -> None:
        """Spec with components but no inputs/outputs → identifies gaps."""
        spec_dict = {
            "name": "Test",
            "problem_statement": "Need something",
            "components": [
                {"name": "Component A", "purpose": "Do thing A"},
                {"name": "Component B", "purpose": "Do thing B"},
            ],
        }

        spec = InterviewSpec.model_validate(spec_dict)
        result = validate_spec(spec)

        # Should flag missing inputs/outputs
        input_gaps = [g for g in result.gaps if "input" in g.field]
        output_gaps = [g for g in result.gaps if "output" in g.field]

        assert len(input_gaps) > 0
        assert len(output_gaps) > 0

    def test_spec_file_with_invalid_schema(self, tmp_path: Path) -> None:
        """Spec file with data that doesn't match schema → ValueError."""
        bad_spec = {
            "name": "Test",
            "components": [{"name": "Component", "invalid_field": "bad"}],
        }

        spec_file = tmp_path / "bad_schema.json"
        spec_file.write_text(json.dumps(bad_spec))

        # validate_spec_file should raise ValueError for schema mismatch
        with pytest.raises(ValueError, match="schema"):
            validate_spec_file(spec_file)


class TestMetadataHandling:
    """Integration tests for metadata in specs."""

    def test_spec_with_metadata_round_trip(self) -> None:
        """Spec with metadata → serialize → deserialize → metadata preserved."""
        spec_dict = {
            "name": "Test",
            "problem_statement": "Problem",
            "metadata": {
                "interview_date": "2026-02-13",
                "mode": "direct",
                "completeness_score": 85,
                "domain": "software-requirements",
                "question_count": 12,
            },
        }

        spec1 = InterviewSpec.model_validate(spec_dict)
        assert spec1.metadata is not None
        assert spec1.metadata.mode == InterviewMode.DIRECT

        # Round trip
        json_str = spec1.model_dump_json()
        spec2 = InterviewSpec.model_validate_json(json_str)

        assert spec2.metadata is not None
        assert spec2.metadata.interview_date == date(2026, 2, 13)
        assert spec2.metadata.question_count == 12

    def test_spec_without_metadata_valid(self) -> None:
        """Spec without metadata → still valid."""
        spec_dict = {
            "name": "Test",
            "problem_statement": "Problem",
        }

        spec = InterviewSpec.model_validate(spec_dict)

        assert spec.metadata is None
        # Should still be able to validate
        result = validate_spec(spec)
        assert isinstance(result, CompletenessResult)


class TestStakeholderProfileHandling:
    """Integration tests for stakeholder profile in specs."""

    def test_spec_with_stakeholder_profile_scores_bonus(self) -> None:
        """Spec with stakeholder_profile → gets 5 bonus points."""
        base_dict = {
            "name": "Test",
            "problem_statement": "Need authentication",
            "components": [
                {
                    "name": "Auth",
                    "purpose": "Handle auth",
                    "inputs": ["credentials"],
                    "outputs": ["token"],
                }
            ],
        }

        spec_without = InterviewSpec.model_validate(base_dict)
        result_without = validate_spec(spec_without)

        # Add stakeholder profile
        with_profile = base_dict.copy()
        with_profile["stakeholder_profile"] = {
            "working_style": "terminal",
            "values": ["speed"],
            "pain_points": ["slow deploys"],
            "priorities": ["automation"],
            "technical_preferences": ["Python"],
        }

        spec_with = InterviewSpec.model_validate(with_profile)
        result_with = validate_spec(spec_with)

        # Should score 5 points higher
        assert result_with.score == result_without.score + 5

    def test_stakeholder_profile_round_trip(self) -> None:
        """Stakeholder profile → serialize → deserialize → preserved."""
        profile = StakeholderProfile(
            working_style="IDE-based",
            values=["code quality", "performance"],
            pain_points=["flaky tests"],
            priorities=["reliability first"],
            technical_preferences=["TypeScript", "React"],
        )

        spec = InterviewSpec(
            name="Test",
            problem_statement="Problem",
            stakeholder_profile=profile,
        )

        # Round trip
        json_str = spec.model_dump_json()
        restored = InterviewSpec.model_validate_json(json_str)

        assert restored.stakeholder_profile is not None
        assert restored.stakeholder_profile.working_style == "IDE-based"
        assert len(restored.stakeholder_profile.values) == 2
