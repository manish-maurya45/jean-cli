"""

One policy - read what the OS allows, write only inside the project, no network -
and a different enforcement mechanism per OS. The idea ports; the mechanism never does.

  macOS    Seatbelt (sandbox-exec) profile
  Linux    bubblewrap (bwrap) mount + network namespaces
  Windows  AppContainer token + ACLs + job object

"""

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from ctypes import wintypes
from pathlib import Path

PROJECT = Path.cwd().resolve()

PROFILE = f"""(version 1)
(deny default)
(allow process-exec process-fork signal)
(allow file-read*)
(allow sysctl-read)
(deny network*)
(allow file-write* (subpath "{PROJECT}") (literal "/dev/null"))
(deny file-write* (subpath "{PROJECT}/.git"))
"""


# --------------------------------------------------------------------------
# macOS / Linux: wrap the command in an argv prefix
# --------------------------------------------------------------------------

def wrap(command):
    """Wrap a shell command in an OS sandbox (macOS/Linux). None means no wrapper."""
    if sys.platform == "darwin":
        profile = Path(tempfile.gettempdir()) / "jeancli.sb"
        profile.write_text(PROFILE)
        return ["sandbox-exec", "-f", str(profile), "/bin/sh", "-c", command]

    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return [
            "bwrap",
            "--ro-bind", "/", "/",
            "--bind", str(PROJECT), str(PROJECT),
            "--dev", "/dev", "--proc", "/proc",
            "--unshare-net", "--die-with-parent",
            "/bin/sh", "-c", command,
        ]

    return None  # Windows (handled separately) or Linux without bubblewrap


# --------------------------------------------------------------------------
# Windows: AppContainer
# --------------------------------------------------------------------------

_APPC_NAME = "jean_cli.sandbox"
_win_state = None  # (sid pointer, sid string, kernel32), set up once per process


def _win_setup():
    """Create the AppContainer profile, grant it the project, set up Win32 prototypes."""
    global _win_state
    if _win_state:
        return _win_state

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)

    H, P, D = wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD
    k.CreatePipe.argtypes = [P, P, P, D]
    k.SetHandleInformation.argtypes = [H, D, D]
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, D, D, P, D, D, H]
    k.CreateFileW.restype = H
    k.CreateJobObjectW.argtypes = [P, wintypes.LPCWSTR]
    k.CreateJobObjectW.restype = H
    k.SetInformationJobObject.argtypes = [H, ctypes.c_int, P, D]
    k.AssignProcessToJobObject.argtypes = [H, H]
    k.TerminateJobObject.argtypes = [H, wintypes.UINT]
    k.InitializeProcThreadAttributeList.argtypes = [P, D, D, P]
    k.UpdateProcThreadAttribute.argtypes = [P, D, P, P, ctypes.c_size_t, P, P]
    k.DeleteProcThreadAttributeList.argtypes = [P]
    k.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, P, P, wintypes.BOOL,
                                 D, P, wintypes.LPCWSTR, P, P]
    k.ResumeThread.argtypes = [H]
    k.WaitForSingleObject.argtypes = [H, D]
    k.GetExitCodeProcess.argtypes = [H, P]
    k.ReadFile.argtypes = [H, P, D, P, P]
    k.CloseHandle.argtypes = [H]
    userenv.CreateAppContainerProfile.restype = ctypes.c_long
    userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long

    sid = ctypes.c_void_p()
    hr = userenv.CreateAppContainerProfile(
        _APPC_NAME, "jean_cli sandbox", "jean_cli bash sandbox", None, 0, ctypes.byref(sid))
    if (hr & 0xFFFFFFFF) == 0x800700B7:  # already exists
        hr = userenv.DeriveAppContainerSidFromAppContainerName(_APPC_NAME, ctypes.byref(sid))
    if hr != 0:
        raise OSError(f"AppContainer setup failed: HRESULT {hr & 0xFFFFFFFF:#x}")

    sid_str = wintypes.LPWSTR()
    if not adv.ConvertSidToStringSidW(sid, ctypes.byref(sid_str)):
        raise ctypes.WinError(ctypes.get_last_error())
    s = sid_str.value

    def icacls(*args):
        subprocess.run(["icacls", *args], capture_output=True, check=True)

    # Write access to the project (inherits to children) ...
    icacls(str(PROJECT), "/grant", f"*{s}:(OI)(CI)M")
    # ... except .git, which stays read-only.
    git = PROJECT / ".git"
    if git.exists():
        icacls(str(git), "/deny", f"*{s}:(OI)(CI)(W,D,DC)")

    _win_state = (sid, s, k)
    return _win_state


class _SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [("AppContainerSid", ctypes.c_void_p), ("Capabilities", ctypes.c_void_p),
                ("CapabilityCount", wintypes.DWORD), ("Reserved", wintypes.DWORD)]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
                ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
                ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
                ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", _STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p),
                ("bInheritHandle", wintypes.BOOL)]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in
                ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]


class _JOB_BASIC(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD)]


class _JOB_EXTENDED(ctypes.Structure):
    _fields_ = [("Basic", _JOB_BASIC), ("Io", _IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


def _drain(k, handle, chunks):
    buf = ctypes.create_string_buffer(65536)
    n = wintypes.DWORD()
    while k.ReadFile(handle, buf, len(buf), ctypes.byref(n), None) and n.value:
        chunks.append(buf.raw[:n.value])


def _run_appcontainer(command, timeout):
    sid, _, k = _win_setup()
    check = lambda ok: ok or (_ for _ in ()).throw(ctypes.WinError(ctypes.get_last_error()))

    # Job object: kills the whole process tree on timeout or when we exit.
    job = k.CreateJobObjectW(None, None)
    info = _JOB_EXTENDED()
    info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    check(k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)))

    # Inheritable pipes for stdout/stderr, NUL for stdin.
    sa = _SECURITY_ATTRIBUTES(ctypes.sizeof(_SECURITY_ATTRIBUTES), None, True)
    ends = {}
    for name_ in ("out", "err"):
        r, w = wintypes.HANDLE(), wintypes.HANDLE()
        check(k.CreatePipe(ctypes.byref(r), ctypes.byref(w), ctypes.byref(sa), 0))
        check(k.SetHandleInformation(r, 1, 0))  # parent's read end is not inherited
        ends[name_] = (r, w)
    nul = k.CreateFileW("NUL", 0x80000000, 3, ctypes.byref(sa), 3, 0, None)

    # Attach the AppContainer security capabilities (no capabilities = no network).
    caps = _SECURITY_CAPABILITIES(sid, None, 0, 0)
    size = ctypes.c_size_t()
    k.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    attr_buf = ctypes.create_string_buffer(size.value)
    check(k.InitializeProcThreadAttributeList(attr_buf, 1, 0, ctypes.byref(size)))
    check(k.UpdateProcThreadAttribute(attr_buf, 0, 0x20009, ctypes.byref(caps),
                                      ctypes.sizeof(caps), None, None))

    si = _STARTUPINFOEXW()
    si.StartupInfo.cb = ctypes.sizeof(si)
    si.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES
    si.StartupInfo.hStdInput = nul
    si.StartupInfo.hStdOutput = ends["out"][1]
    si.StartupInfo.hStdError = ends["err"][1]
    si.lpAttributeList = ctypes.cast(attr_buf, ctypes.c_void_p)

    cmdline = ctypes.create_unicode_buffer(
        f'"{os.environ.get("COMSPEC", "cmd.exe")}" /d /s /c "{command}"')
    pi = _PROCESS_INFORMATION()
    # EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW | CREATE_SUSPENDED
    flags = 0x00080000 | 0x08000000 | 0x00000004
    try:
        check(k.CreateProcessW(None, cmdline, None, None, True, flags, None,
                               str(PROJECT), ctypes.byref(si), ctypes.byref(pi)))
    finally:
        k.CloseHandle(ends["out"][1])
        k.CloseHandle(ends["err"][1])
        k.CloseHandle(nul)
        k.DeleteProcThreadAttributeList(attr_buf)

    k.AssignProcessToJobObject(job, pi.hProcess)
    k.ResumeThread(pi.hThread)
    k.CloseHandle(pi.hThread)

    out, err = [], []
    threads = [threading.Thread(target=_drain, args=(k, ends["out"][0], out)),
               threading.Thread(target=_drain, args=(k, ends["err"][0], err))]
    for t in threads:
        t.start()

    timed_out = k.WaitForSingleObject(pi.hProcess, int(timeout * 1000)) == 0x102
    if timed_out:
        k.TerminateJobObject(job, 1)
    for t in threads:
        t.join()

    code = wintypes.DWORD()
    k.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
    for h in (pi.hProcess, ends["out"][0], ends["err"][0], job):  # closing job kills stragglers
        k.CloseHandle(h)

    stdout = b"".join(out).decode(errors="replace")
    stderr = b"".join(err).decode(errors="replace")
    if timed_out:
        raise subprocess.TimeoutExpired(command, timeout, stdout, stderr)
    return subprocess.CompletedProcess(command, code.value, stdout, stderr)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def name():
    if sys.platform == "darwin":
        return "seatbelt"
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return "bubblewrap"
    if sys.platform == "win32":
        return "appcontainer"
    return "none"


def run(command, timeout=60):
    """Run a command, sandboxed when the OS lets us."""
    if sys.platform == "win32":
        return _run_appcontainer(command, timeout)

    sandboxed = wrap(command)
    return subprocess.run(
        sandboxed or command,
        shell=sandboxed is None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )