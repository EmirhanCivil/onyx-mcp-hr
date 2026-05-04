import asyncio

from app.server import mcp


def test_hr_intelligence_tools_registered():
    async def run():
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        expected = {
            "auto_select_hr_file",
            "normalize_hr_columns",
            "calculate_hr_data_quality_score",
            "explain_hr_query_plan",
            "generate_hr_overview_dashboard",
            "analyze_candidate_stage_transitions",
            "analyze_position_funnel",
            "compare_candidate_segments",
            "analyze_survey_root_causes",
            "suggest_hr_questions",
        }
        missing = expected - names
        assert not missing

    asyncio.run(run())

