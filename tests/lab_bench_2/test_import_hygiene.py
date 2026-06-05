import subprocess
import sys
import textwrap


def test_package_imports_without_optional_labbench2_dependency() -> None:
    # given a fresh interpreter where the optional ``labbench2`` extra (which
    # provides the ``evals`` / ``labbench2`` modules) cannot be imported
    script = textwrap.dedent(
        """
        import sys

        class _Blocker:
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in {"evals", "labbench2"}:
                    raise ModuleNotFoundError(name)
                return None

        sys.meta_path.insert(0, _Blocker())

        # Importing the package is what Inspect does for entry-point task
        # discovery; it must not pull in the optional dependency.
        import lab_bench_2
        from lab_bench_2 import lab_bench_2 as task, SUPPORTED_TAGS

        assert callable(task)
        assert "litqa3" in SUPPORTED_TAGS
        assert "evals" not in sys.modules
        assert "labbench2" not in sys.modules
        """
    )

    # when the package is imported in that interpreter
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    # then discovery succeeds without the optional dependency installed
    assert result.returncode == 0, result.stderr
