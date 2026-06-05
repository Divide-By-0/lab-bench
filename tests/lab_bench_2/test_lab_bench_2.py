import sys
from typing import Any

import pytest
from inspect_ai._util.registry import registry_info
from inspect_ai.dataset import Dataset, MemoryDataset, Sample

from lab_bench_2.lab_bench_2 import SUPPORTED_TAGS, lab_bench_2

# The package re-exports the ``lab_bench_2`` task, shadowing the submodule of the
# same name as a package attribute; reach the module object via sys.modules so
# monkeypatching its globals works.
task_module = sys.modules["lab_bench_2.lab_bench_2"]


def _fake_dataset() -> Dataset:
    return MemoryDataset(
        samples=[Sample(input="q", target="a", metadata={"tag": "litqa3"})],
        name="fake",
    )


def _metric_names(scorer: Any) -> list[str]:
    """Registry names of the metrics carried by a Task scorer."""
    metrics = registry_info(scorer).metadata["metrics"]
    return [registry_info(metric).name for metric in metrics]


class TestLabBench2Task:
    def test_none_runs_full_set_with_grouped_scorer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given the combined loader stubbed to avoid network
        captured: dict[str, Any] = {}

        def fake_all(tags: Any, mode: str = "file") -> Dataset:
            captured["tags"] = tags
            return _fake_dataset()

        monkeypatch.setattr(task_module, "load_multi_tags_dataset", fake_all)

        # when tags is omitted (defaults to None → every tag)
        sut = lab_bench_2()

        # then every tag is loaded and the scorer groups by tag
        assert captured["tags"] == list(SUPPORTED_TAGS)
        assert sut.scorer is not None
        assert _metric_names(sut.scorer[0]) == [
            "inspect_ai/grouped",
            "inspect_ai/grouped",
        ]

    def test_list_of_tags_uses_grouped_scorer_over_selection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given the combined loader stubbed to avoid network
        captured: dict[str, Any] = {}

        def fake_all(tags: Any, mode: str = "file") -> Dataset:
            captured["tags"] = tags
            return _fake_dataset()

        monkeypatch.setattr(task_module, "load_multi_tags_dataset", fake_all)

        # when a subset list is requested
        sut = lab_bench_2(tags=["litqa3", "cloning"])

        # then only those tags are loaded, scored with the grouped scorer
        assert captured["tags"] == ["litqa3", "cloning"]
        assert sut.scorer is not None
        assert _metric_names(sut.scorer[0]) == [
            "inspect_ai/grouped",
            "inspect_ai/grouped",
        ]

    def test_single_tag_string_uses_its_own_ungrouped_scorer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given the per-tag loader stubbed to avoid network
        def fake_loader(**kwargs: Any) -> Dataset:
            return _fake_dataset()

        monkeypatch.setattr(task_module, "load_lab_bench_2_dataset", fake_loader)

        # when a single tag string is requested
        sut = lab_bench_2(tags="litqa3")

        # then the single-tag scorer is not grouped
        assert sut.scorer is not None
        assert "inspect_ai/grouped" not in _metric_names(sut.scorer[0])

    def test_unknown_tag_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            lab_bench_2(tags="bogusqa")

    def test_unknown_tag_in_list_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            lab_bench_2(tags=["litqa3", "bogusqa"])

    def test_empty_list_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one tag"):
            lab_bench_2(tags=[])
