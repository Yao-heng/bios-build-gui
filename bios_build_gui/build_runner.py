"""Build Runner (Interface I3).

Invokes the EDK II ``build`` command as a subprocess (no shell), streams
stdout/stderr line-by-line to the caller's callback, writes the full
output to a log file, and returns the exit code. Success is defined
solely by exit code 0; the runner does not parse build output for
success or failure.

Environment setup
-----------------
The runner replicates what ``edksetup.sh`` does, without sourcing it:
it sets ``WORKSPACE``, ``PACKAGES_PATH``, ``EDK_TOOLS_PATH``,
``CONF_PATH`` and ``PYTHON_COMMAND`` in the subprocess environment,
derived from the working directory (the EDK II workspace). It also
prepends the BaseTools wrapper directory
(``<workspace>/BaseTools/BinWrappers/PosixLike``) to ``PATH`` so the
``build`` command itself is found — that is the other half of what
``edksetup.sh`` does, and without it ``build`` would not resolve.

Pre-build phase
---------------
When the working directory is an EDK II workspace (it contains
``edksetup.sh``) and the BaseTools binaries are missing, the runner
builds them once (``make -C BaseTools``, output streamed to the log)
and then proceeds. If that fails, the build fails with a clear error
and the build command is not run. In a non-EDK II working directory
(the unit tests' dummy commands) the pre-build phase is skipped.

Cancellation
------------
``cancel_event`` (a ``threading.Event``) is checked between output
lines; when set, the subprocess is terminated and ``run_build`` returns
the (negative) return code of the killed process.

Log retention
-------------
After each run, only the 10 most recent ``build-*.log`` files are kept
in the log file's directory; older ones are removed.
"""

from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path

_ERROR_WORD_RE = re.compile(r"\berror\b", re.IGNORECASE)
_COMPILER_ERROR_RE = re.compile(r"\.c\(\d+\):|\.c:\d+:")
_FAILED_RE = re.compile(r"Failed")
_LOG_KEEP = 10


def run_build(command, workdir, log_path, on_line, cancel_event):
    """Run a build command and return its exit code.

    ``command`` is an argument list (never a shell string). ``workdir``
    is the EDK II workspace. ``log_path`` receives the full output.
    ``on_line`` is called with each output line (on the worker thread).
    ``cancel_event`` is a ``threading.Event`` (or None).
    """
    workdir = Path(workdir).resolve()
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = _build_env(workdir)

    with log_path.open("w", encoding="utf-8") as log_file:

        def emit(line):
            log_file.write(line)
            log_file.flush()
            if on_line is not None:
                on_line(line)

        if _is_edk2_workspace(workdir) and not _basetools_binaries_present(workdir):
            emit("BaseTools binaries not found; building them once (make -C BaseTools)...\n")
            make_rc = _run_make_basetools(workdir, env, emit, cancel_event)
            if make_rc != 0:
                emit(
                    f"ERROR: BaseTools build failed (exit code {make_rc}). "
                    "Run `make -C BaseTools` in the EDK II tree manually.\n"
                )
                _prune_logs(log_path)
                return make_rc

        proc = subprocess.Popen(
            list(command),
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            bufsize=1,
            errors="replace",
            shell=False,
        )
        cancelled = _stream_output(proc, emit, cancel_event)
        if cancelled:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        else:
            proc.wait()
        _prune_logs(log_path)
        return proc.returncode


def _stream_output(proc, emit, cancel_event):
    """Stream the process output to ``emit``; return True if cancelled.

    stdout is read on a reader thread so a long-running command that
    produces no output cannot block the cancellation check.
    """
    lines = queue.Queue()

    def _reader():
        try:
            for line in proc.stdout:
                lines.put(line)
        except ValueError:
            pass
        finally:
            lines.put(None)

    threading.Thread(target=_reader, daemon=True).start()
    while True:
        try:
            item = lines.get(timeout=0.05)
        except queue.Empty:
            if cancel_event is not None and cancel_event.is_set():
                return True
            continue
        if item is None:
            return False
        emit(item)
        if cancel_event is not None and cancel_event.is_set():
            return True


def _run_make_basetools(workdir, env, emit, cancel_event):
    """Build the BaseTools binaries once; return the exit code."""
    proc = subprocess.Popen(
        ["make", "-C", "BaseTools"],
        cwd=str(workdir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
        bufsize=1,
        errors="replace",
        shell=False,
    )
    _stream_output(proc, emit, cancel_event)
    proc.wait()
    return proc.returncode


def _build_env(workdir):
    """Replicate edksetup.sh's environment for the subprocess."""
    env = dict(os.environ)
    env["WORKSPACE"] = str(workdir)
    env["PACKAGES_PATH"] = str(workdir)
    env["EDK_TOOLS_PATH"] = str(workdir / "BaseTools")
    env["CONF_PATH"] = str(workdir / "Conf")
    env["PYTHON_COMMAND"] = sys.executable
    wrappers = str(workdir / "BaseTools" / "BinWrappers" / "PosixLike")
    env["PATH"] = wrappers + os.pathsep + env.get("PATH", "")
    return env


def _is_edk2_workspace(workdir):
    return (workdir / "edksetup.sh").is_file()


def _basetools_binaries_present(workdir):
    return (workdir / "BaseTools" / "BinWrappers" / "PosixLike" / "build").is_file()


def _prune_logs(log_path, keep=_LOG_KEEP):
    """Keep only the newest ``keep`` build-*.log files in the log directory."""
    parent = Path(log_path).parent
    try:
        logs = sorted(
            parent.glob("build-*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return
    for old in logs[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def extract_error_block(log_path) -> str:
    """Extract the error block from a build log.

    Scan the log from the end backwards; find the last line matching an
    error pattern; the block is that line plus the 20 lines preceding it
    and the 5 lines following it (if any). Error patterns: (a) a line
    containing ``error`` (case-insensitive) as a word; (b) a compiler
    error with file/line (``*.c(123):`` or ``*.c:123:``); (c) a line
    containing ``Failed``. If no line matches, fall back to the last 30
    lines of the log. Each line is prefixed with its 1-based log line
    number.
    """
    lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return ""
    match_idx = None
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if (
            _ERROR_WORD_RE.search(line)
            or _COMPILER_ERROR_RE.search(line)
            or _FAILED_RE.search(line)
        ):
            match_idx = i
            break
    if match_idx is None:
        start = max(0, len(lines) - 30)
        end = len(lines)
    else:
        start = max(0, match_idx - 20)
        end = min(len(lines), match_idx + 6)
    block = lines[start:end]
    return "\n".join(f"{start + j + 1}: {text}" for j, text in enumerate(block))
