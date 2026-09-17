from app.api.routes.templates import PROJECT_TEMPLATES, TASK_TEMPLATES


def test_required_task_templates_exist():
    assert set(TASK_TEMPLATES) == {
        "bug-report",
        "feature-request",
        "code-review",
        "marketing-task",
    }
    for template in TASK_TEMPLATES.values():
        assert template["name"]
        assert template["description"]
        assert template["priority"] in {"urgent", "high", "medium", "low", "none"}
        assert template["labels"]
        assert template["checklists"]


def test_required_project_templates_are_structurally_valid():
    assert set(PROJECT_TEMPLATES) == {
        "software-development",
        "product-launch",
        "marketing-campaign",
        "university-project",
    }
    for template in PROJECT_TEMPLATES.values():
        columns = set(template["columns"])
        labels = {name for name, _ in template["labels"]}
        assert len(columns) >= 4
        for _, column_name, priority, label_name in template["tasks"]:
            assert column_name in columns
            assert priority in {"urgent", "high", "medium", "low", "none"}
            assert label_name is None or label_name in labels
