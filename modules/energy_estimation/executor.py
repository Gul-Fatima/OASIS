import os
import subprocess
import tempfile
import time

import psutil


class ProjectExecutor:
    """
    Executes the target project as a managed subprocess.

    Supports long-running / infinite processes (e.g. a PHP website
    served by `php -S`): the process is started with start(), polled
    with poll(), and can be terminated early with stop() instead of
    only dying when the timeout expires.
    """

    def __init__(
        self,
        command: str,
        working_directory: str,
        timeout: int = 300,
    ):
        self.command = command
        self.working_directory = working_directory
        self.timeout = timeout
        self.process = None
        self._start_time = None
        self._stdout_file = None
        self._stderr_file = None

    # --------------------------------------------------------
    # PROCESS CONTROL
    # --------------------------------------------------------

    def start(self):
        """Start the project process without blocking."""

        print()
        print("=" * 60)
        print("           STARTING PROJECT")
        print("=" * 60)
        print(f"Working Directory : {self.working_directory}")
        print(f"Command           : {self.command}")

        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"

        # stdout/stderr go to temp files so long-running
        # processes cannot fill OS pipes and block.
        self._start_time = time.perf_counter()

        try:
            self._stdout_file = tempfile.TemporaryFile(
                mode="w+",
                encoding="utf-8",
                errors="replace",
            )
            self._stderr_file = tempfile.TemporaryFile(
                mode="w+",
                encoding="utf-8",
                errors="replace",
            )

            self.process = subprocess.Popen(
                self.command,
                cwd=self.working_directory,
                shell=True,
                stdout=self._stdout_file,
                stderr=self._stderr_file,
                env=environment,
            )

            print(f"Process started with PID : {self.process.pid}")
            return True

        except Exception as e:
            print("Failed to start project:", str(e))
            self.process = None
            return False

    def is_running(self) -> bool:
        """True while the managed subprocess is still alive."""

        if self.process is None:
            return False

        return self.process.poll() is None

    def poll(self):
        """Return running / timeout status for the managed process."""

        if self.process is None:
            return {
                "running": False,
                "return_code": None,
                "elapsed_seconds": 0,
                "timed_out": False,
            }

        return_code = self.process.poll()
        elapsed = time.perf_counter() - self._start_time

        timed_out = (
            return_code is None
            and self.timeout is not None
            and elapsed > self.timeout
        )

        return {
            "running": return_code is None,
            "return_code": return_code,
            "elapsed_seconds": elapsed,
            "timed_out": timed_out,
        }

    def stop(self):
        """
        Stop the project process and its whole process tree
        (e.g. PHP workers spawned by the server).
        """

        if self.process is None:
            return {
                "return_code": None,
                "stdout": "",
                "stderr": "Process was never started.",
                "stopped_by_user": False,
                "pid": None,
                "running": False,
            }

        stopped_by_user = self.process.poll() is None
        pid = self.process.pid

        if stopped_by_user:
            self._kill_process_tree(pid)

        try:
            return_code = self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            return_code = self.process.wait()

        elapsed = time.perf_counter() - self._start_time

        print()
        print("=" * 60)
        print("           PROJECT STOPPED")
        print("=" * 60)
        print(f"Return Code : {return_code}")
        print(f"Elapsed     : {elapsed:.2f} seconds")

        stdout, stderr = self.get_output()
        self._close_output_files()
        self.process = None

        return {
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "elapsed_seconds": elapsed,
            "stopped_by_user": stopped_by_user,
            "pid": pid,
            "running": False,
        }

    def get_output(self, max_chars: int = 4000):
        """Return truncated (stdout, stderr) captured so far."""

        if self._stdout_file is None:
            return "", ""

        def read_tail(handle):
            try:
                handle.seek(0)
                content = handle.read()
                return content[-max_chars:]
            except Exception:
                return ""

        return (
            read_tail(self._stdout_file),
            read_tail(self._stderr_file),
        )

    def _close_output_files(self):
        for handle in (self._stdout_file, self._stderr_file):
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass

        self._stdout_file = None
        self._stderr_file = None

    def _kill_process_tree(self, pid: int):
        """
        Kill a process and all of its children.

        A shell command like `php -S ...` spawns the real server
        as a child of the shell, so killing only the shell would
        leave PHP running.
        """

        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
        except psutil.NoSuchProcess:
            return

        for child in children:
            self._terminate_or_kill(child)

        self._terminate_or_kill(parent)

    @staticmethod
    def _terminate_or_kill(process):
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            return

        try:
            process.wait(timeout=3)
        except psutil.TimeoutExpired:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass

    # --------------------------------------------------------
    # LEGACY BLOCKING EXECUTION
    # --------------------------------------------------------

    def execute(self):
        print()
        print("=" * 60)
        print("           STARTING PROJECT (BLOCKING)")
        print("=" * 60)
        print(f"Working Directory : {self.working_directory}")
        print(f"Command           : {self.command}")

        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"

        try:
            result = subprocess.run(
                self.command,
                cwd=self.working_directory,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=self.timeout,
            )

            print(f"Return Code : {result.returncode}")

            return {
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired:
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": "Project execution timed out.",
            }

        except Exception as e:
            return {
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
            }
