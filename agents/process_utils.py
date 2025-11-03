# ~/governor_ai/agents/process_utils.py
import os
import signal
import subprocess
from typing import Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.path.join(BASE_DIR, "logs")
PID_DIR = os.path.join(BASE_DIR, "run")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(PID_DIR, exist_ok=True)

def _pid_path(name: str) -> str:
    return os.path.join(PID_DIR, f"{name}.pid")

def _log_paths(name: str):
    stdout_path = os.path.join(LOG_DIR, f"{name}.out.log")
    stderr_path = os.path.join(LOG_DIR, f"{name}.err.log")
    return stdout_path, stderr_path

def is_running(name: str) -> bool:
    pid = read_pid(name)
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False

def read_pid(name: str) -> Optional[int]:
    try:
        with open(_pid_path(name), "r") as f:
            return int(f.read().strip())
    except Exception:
        return None

def write_pid(name: str, pid: int):
    with open(_pid_path(name), "w") as f:
        f.write(str(pid))

def remove_pid(name: str):
    try:
        os.remove(_pid_path(name))
    except FileNotFoundError:
        pass

def start_process(name: str, cmd: list, env: dict = None) -> int:
    if is_running(name):
        return read_pid(name)

    stdout_path, stderr_path = _log_paths(name)
    stdout_f = open(stdout_path, "a")
    stderr_f = open(stderr_path, "a")

    proc = subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        stdout=stdout_f,
        stderr=stderr_f,
        stdin=subprocess.DEVNULL,
        env=env or os.environ.copy(),
        preexec_fn=os.setsid,  # own process group for easier stopping
    )
    write_pid(name, proc.pid)
    return proc.pid

def stop_process(name: str, graceful_secs: int = 5) -> bool:
    pid = read_pid(name)
    if not pid:
        return False
    try:
        # SIGTERM group
        os.killpg(pid, signal.SIGTERM)
    except Exception:
        pass

    for _ in range(graceful_secs * 10):
        if not is_running(name):
            remove_pid(name)
            return True
        try:
            os.kill(pid, 0)
        except Exception:
            remove_pid(name)
            return True

    # force kill
    try:
        os.killpg(pid, signal.SIGKILL)
    except Exception:
        pass

    remove_pid(name)
    return True
