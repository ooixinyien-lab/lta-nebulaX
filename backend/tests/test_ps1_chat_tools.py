"""Tests for read-only chat tools and strict enforcement of the allowlist."""
from pathlib import Path
import pytest
from backend.app.auth.resource_access import ChatScope
from backend.app.ps1.chat_tools import ALLOWLISTED_TOOLS, ScheduleReadTools
from backend.app.ps1.explanations import FixtureExplanationSource

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "chat"


@pytest.fixture
def chat_scope():
    return ChatScope(
        instance_id="inst-test",
        instance_revision_id="rev-test",
        run_id="run-disrupted-002",
        baseline_run_id="run-baseline-001",
        scenario="A",
        user_id="demo-officer",
        user_role="officer",
    )


@pytest.fixture
def read_tools():
    source = FixtureExplanationSource(FIXTURES_DIR)
    return ScheduleReadTools(source)


def test_allowlisted_tools_execute_correctly(read_tools, chat_scope):
    # 1. get_run_summary
    res, evidence = read_tools.execute_tool(chat_scope, "get_run_summary", {})
    assert res["run_id"] == "run-disrupted-002"
    assert res["scenario"] == "A"
    assert len(evidence) == 1

    # 2. get_activity
    res, evidence = read_tools.execute_tool(chat_scope, "get_activity", {"activity_id": "A017"})
    assert res["activity_id"] == "A017"
    assert len(evidence) == 1

    # 3. get_activity_diff
    res, evidence = read_tools.execute_tool(chat_scope, "get_activity_diff", {"activity_id": "A017"})
    assert res["available"] is True
    assert res["week_displacement"] == 2
    assert len(evidence) == 1
    assert evidence[0].entity_type == "run_diff"

    # 4. get_run_conflicts
    res, evidence = read_tools.execute_tool(chat_scope, "get_run_conflicts", {"activity_id": "A017"})
    assert len(res["conflicts"]) == 1
    assert len(evidence) == 1
    assert evidence[0].entity_type == "conflict"

    # 5. get_counterfactuals
    res, evidence = read_tools.execute_tool(chat_scope, "get_counterfactuals", {"activity_id": "A017"})
    assert len(res["counterfactuals"]) == 1
    assert res["counterfactuals"][0]["result"] == "INFEASIBLE"


@pytest.mark.parametrize("prohibited_tool", [
    "solve_schedule",
    "replan",
    "validate_schedule",
    "edit_activity",
    "move_activity",
    "pin_activity",
    "save_plan",
    "publish_plan",
    "execute_sql",
    "run_query",
    "upload_file",
    "delete_data",
])
def test_prohibited_tools_fail_closed(read_tools, chat_scope, prohibited_tool):
    assert prohibited_tool not in ALLOWLISTED_TOOLS
    with pytest.raises(PermissionError, match="not in the read-only allowlist"):
        read_tools.execute_tool(chat_scope, prohibited_tool, {})
