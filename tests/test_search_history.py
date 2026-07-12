from app.services.search_history import SearchHistoryService


def test_history_add_dedupes_and_keeps_latest(tmp_path):
    service = SearchHistoryService(history_path=tmp_path / "history.json", max_entries=3)
    service.add("science", result_count=2, mode="demo")
    service.add("math", result_count=4, mode="demo")
    service.add("Science", result_count=5, mode="live")

    items = service.list_entries()
    assert [item.query for item in items] == ["Science", "math"]
    assert items[0].result_count == 5
    assert items[0].mode == "live"


def test_history_respects_max_entries(tmp_path):
    service = SearchHistoryService(history_path=tmp_path / "history.json", max_entries=2)
    service.add("one", result_count=1, mode="demo")
    service.add("two", result_count=1, mode="demo")
    service.add("three", result_count=1, mode="demo")

    assert [item.query for item in service.list_entries()] == ["three", "two"]
