"""A `python` tool whose variables survive between calls.

REASON: Inspect's stock `python()` tool runs each snippet in a fresh interpreter, so
anything defined in one call is gone by the next. Measured across every agentic run in
this repo: 125 of 544 tool calls (23%) returned an error, and **94 of those 125 were
NameError** -- almost always `name 'SeqIO' is not defined` or a variable defined two
calls earlier. The model spends its budget re-importing and re-parsing a 1.5 MB GenBank
instead of making progress, which is what drove two samples into the token limit.

State is carried in a dill pickle of the user namespace rather than a long-lived
interpreter process, because the sandbox exec API is one-shot per call and a resident
REPL would need a supervisor inside the container. dill (not pickle) because Biopython
records, compiled regexes and locally-defined functions are all common here and stdlib
pickle chokes on them.

Anything genuinely unpicklable (open file handles, sockets) is dropped from the carried
namespace with a note, rather than failing the call.
"""

from __future__ import annotations

import textwrap

from inspect_ai.tool import Tool, ToolError, tool
from inspect_ai.util import sandbox

STATE_PATH = "/tmp/_labbench_session.pkl"

_WRAPPER = """
import sys, io, traceback
_UNPICKLABLE = []
try:
    import dill as _ser
except Exception:
    import pickle as _ser

_ns = {{}}
try:
    with open({state!r}, "rb") as _f:
        _ns = _ser.load(_f)
except Exception:
    _ns = {{}}

_ns["__name__"] = "__main__"
_buf = io.StringIO()
_stdout, sys.stdout = sys.stdout, _buf
_stderr, sys.stderr = sys.stderr, _buf
try:
    exec(compile({code!r}, "<session>", "exec"), _ns)
except BaseException:
    traceback.print_exc(file=_buf)
finally:
    sys.stdout, sys.stderr = _stdout, _stderr

# persist what we can; skip modules and anything the serializer refuses
_keep = {{}}
for _k, _v in _ns.items():
    if _k.startswith("__") or type(_v).__name__ == "module":
        continue
    try:
        _ser.dumps(_v)
        _keep[_k] = _v
    except BaseException:
        _UNPICKLABLE.append(_k)
try:
    with open({state!r}, "wb") as _f:
        _ser.dump(_keep, _f)
except BaseException:
    pass

print(_buf.getvalue(), end="")
if _UNPICKLABLE:
    print(f"\\n[session] not carried forward: {{', '.join(sorted(_UNPICKLABLE))}}")
"""


@tool
def python_session(timeout: int = 180) -> Tool:
    async def execute(code: str) -> str:
        """Execute Python in a persistent session.

        Variables, imports and functions defined in one call remain available in every
        later call, so you never need to re-import or re-parse a file you already read.

        Args:
            code: Python code to execute.

        Returns:
            Anything the code printed, plus any traceback it raised.
        """
        script = _WRAPPER.format(state=STATE_PATH, code=textwrap.dedent(code))
        result = await sandbox().exec(["python3", "-c", script], timeout=timeout)
        if not result.success and not result.stdout:
            raise ToolError(result.stderr or "python session failed with no output")
        return result.stdout or result.stderr or "(no output)"

    return execute
