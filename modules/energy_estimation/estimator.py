import os
import threading
import time

import pandas as pd
from codecarbon import EmissionsTracker


class EnergyEstimator:

    def __init__(self, output_dir="results"):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.emissions_file = os.path.join(
            self.output_dir,
            "emissions.csv",
        )

        # ----------------------------------------------------
        # STOP SIGNAL for long-running / infinite processes.
        # The backend sets it through request_stop() when the
        # user presses the Stop button in the dashboard.
        # ----------------------------------------------------
        self._stop_event = threading.Event()

    # ========================================================
    # STOP CONTROL
    # ========================================================

    def request_stop(self):
        """Ask a running measurement to finish early."""
        self._stop_event.set()

    def is_stop_requested(self):
        return self._stop_event.is_set()

    def reset_stop(self):
        self._stop_event.clear()

    # ========================================================
    # FINITE PROCESSES
    # ========================================================

    def estimate(self, executor):
        """Measure energy for a finite process (waits until exit)."""

        print()
        print("=" * 60)
        print("           STARTING ENERGY MEASUREMENT")
        print("=" * 60)

        tracker = EmissionsTracker(
            project_name="OASIS",
            output_dir=self.output_dir,
            save_to_file=True,
            log_level="error",
            measure_power_secs=10,
            allow_multiple_runs=True,
        )

        start_time = time.perf_counter()
        execution_result = None

        try:
            tracker.start()
            execution_result = executor.execute(
                should_stop=self.is_stop_requested
            )
        finally:
            tracker.stop()

        end_time = time.perf_counter()
        execution_time = end_time - start_time

        stopped_by_user = bool(execution_result.get("stopped_by_user"))
        timed_out = bool(execution_result.get("timed_out"))

        cleaned_result = self._read_latest_measurement()
        cleaned_result = self._attach_execution_info(
            cleaned_result,
            execution_result,
            execution_time,
            continuous=False,
            snapshot_index=1,
            stop_reason=(
                "stopped_by_user"
                if stopped_by_user
                else "timeout"
                if timed_out
                else None
            ),
            stopped_by_user=stopped_by_user,
        )

        self._print_summary(cleaned_result, execution_time)
        return cleaned_result

    # ========================================================
    # INFINITE / LONG-RUNNING PROCESSES
    # ========================================================

    def estimate_continuous(
        self,
        executor,
        interval_seconds: int = 10,
        duration_seconds: int = 300,
    ):
        """
        Measure energy for a long-running / infinite process.

        Starts the process, then flushes CodeCarbon metrics every
        ``interval_seconds`` (default 10s) until the duration elapses,
        the process exits, or request_stop() is called (Stop button).
        Yields one metrics dict per flush. The last snapshot has
        ``final: true``.
        """

        self.reset_stop()

        print()
        print("=" * 60)
        print("     STARTING CONTINUOUS ENERGY MEASUREMENT")
        print("=" * 60)
        print(f"Flush interval : {interval_seconds}s")
        print(f"Monitor for    : {duration_seconds}s")

        tracker = EmissionsTracker(
            project_name="OASIS",
            output_dir=self.output_dir,
            save_to_file=True,
            log_level="error",
            measure_power_secs=interval_seconds,
            allow_multiple_runs=True,
        )

        start_time = time.perf_counter()
        snapshot_index = 0
        stop_reason = "duration"
        stopped_by_user = False
        stop_result = {
            "return_code": -1,
            "stdout": "",
            "stderr": "Continuous measurement did not finish.",
            "running": False,
        }

        try:
            tracker.start()

            started = executor.start()

            # Compat: start() may return bool (current executor)
            # or a dict with "running" (older shape).
            if isinstance(started, dict):
                running = bool(started.get("running"))
                pid = started.get("pid")
            else:
                running = bool(started)
                pid = getattr(executor.process, "pid", None)

            if not running:
                tracker.flush()
                end_time = time.perf_counter()
                cleaned = self._read_latest_measurement()
                cleaned = self._attach_execution_info(
                    cleaned,
                    {
                        "return_code": -1,
                        "stdout": "",
                        "stderr": "Process failed to start.",
                        "pid": pid,
                        "running": False,
                    },
                    end_time - start_time,
                    continuous=True,
                    snapshot_index=1,
                    final=True,
                    stop_reason="process_failed_to_start",
                )
                yield cleaned
                return

            deadline = start_time + duration_seconds

            while time.perf_counter() < deadline:
                remaining = deadline - time.perf_counter()
                sleep_for = min(interval_seconds, remaining)

                if sleep_for <= 0:
                    break

                time.sleep(sleep_for)

                status = executor.poll()

                if not status.get("running"):
                    print(
                        "Process exited during continuous monitoring."
                    )
                    stop_reason = "process_exited"
                    break

                if status.get("timed_out"):
                    print(
                        "Monitor duration reached; stopping process."
                    )
                    stop_reason = "duration"
                    break

                if self._stop_event.is_set():
                    print(
                        "Stop requested; stopping process."
                    )
                    stop_reason = "stopped_by_user"
                    break

                tracker.flush()
                snapshot_index += 1

                now = time.perf_counter()
                cleaned = self._read_latest_measurement()
                cleaned = self._attach_execution_info(
                    cleaned,
                    {
                        "return_code": None,
                        "stdout": "",
                        "stderr": "",
                        "pid": pid,
                        "running": True,
                    },
                    now - start_time,
                    continuous=True,
                    snapshot_index=snapshot_index,
                    final=False,
                )

                print()
                print("-" * 60)
                print(
                    f"  Snapshot #{snapshot_index} "
                    f"@ {cleaned['execution_time_seconds']:.1f}s"
                )
                print(
                    f"  Energy : "
                    f"{cleaned.get('energy_consumed')} kWh"
                )
                print(
                    f"  CO2    : "
                    f"{cleaned.get('emissions')} kg"
                )
                print("-" * 60)

                yield cleaned

        finally:
            try:
                tracker.stop()
            except Exception as e:
                print("CodeCarbon stop warning:", e)

            try:
                stop_result = executor.stop()
            except Exception as e:
                stop_result = {
                    "return_code": -1,
                    "stdout": "",
                    "stderr": str(e),
                    "running": False,
                }

        stopped_by_user = stop_reason == "stopped_by_user"
        end_time = time.perf_counter()
        snapshot_index += 1

        try:
            final = self._read_latest_measurement()
        except RuntimeError:
            # If no CSV row yet (very short run), still return status.
            final = {
                "energy_consumed": None,
                "emissions": None,
            }

        final = self._attach_execution_info(
            final,
            stop_result,
            end_time - start_time,
            continuous=True,
            snapshot_index=snapshot_index,
            final=True,
            stop_reason=stop_reason,
            stopped_by_user=stopped_by_user,
        )

        self._print_summary(
            final,
            end_time - start_time,
            continuous=True,
        )
        yield final

    # ========================================================
    # INTERNAL HELPERS
    # ========================================================

    def _read_latest_measurement(self):
        if not os.path.exists(self.emissions_file):
            raise RuntimeError(
                "CodeCarbon did not create emissions.csv"
            )

        try:
            df = pd.read_csv(self.emissions_file)
        except Exception as e:
            raise RuntimeError(
                f"Could not read CodeCarbon emissions.csv: {e}"
            )

        if df.empty:
            raise RuntimeError(
                "CodeCarbon emissions.csv is empty."
            )

        latest = df.iloc[-1].to_dict()
        cleaned_result = {}

        for key, value in latest.items():
            if pd.isna(value):
                cleaned_result[key] = None
            else:
                if hasattr(value, "item"):
                    value = value.item()
                cleaned_result[key] = value

        return cleaned_result

    def _attach_execution_info(
        self,
        cleaned_result,
        execution_result,
        execution_time,
        continuous=False,
        snapshot_index=1,
        final=True,
        stop_reason=None,
        stopped_by_user=False,
    ):
        cleaned_result["execution_time_seconds"] = execution_time
        cleaned_result["return_code"] = execution_result.get(
            "return_code"
        )
        cleaned_result["stdout"] = execution_result.get(
            "stdout", ""
        )
        cleaned_result["stderr"] = execution_result.get(
            "stderr", ""
        )
        cleaned_result["continuous"] = continuous
        cleaned_result["snapshot_index"] = snapshot_index
        cleaned_result["final"] = final
        cleaned_result["pid"] = execution_result.get("pid")
        cleaned_result["process_running"] = execution_result.get(
            "running", False
        )
        cleaned_result["stop_reason"] = stop_reason
        cleaned_result["stopped_by_user"] = stopped_by_user

        if continuous and not final:
            cleaned_result["execution_status"] = "monitoring"
            cleaned_result["baseline_valid"] = True
        elif stopped_by_user or (continuous and stop_reason == "duration"):
            # A user-stopped infinite process is a SUCCESS:
            # measurement ran until the user decided to stop.
            # Likewise a run that reached the full monitor duration:
            # the process was healthy the whole time, the window just
            # ended (the non-zero return code is only our own kill).
            cleaned_result["execution_status"] = "success"
            cleaned_result["baseline_valid"] = True
        elif execution_result.get("return_code") == 0:
            cleaned_result["execution_status"] = "success"
            cleaned_result["baseline_valid"] = True
        else:
            cleaned_result["execution_status"] = "failed"
            cleaned_result["baseline_valid"] = False

        return cleaned_result

    def _print_summary(
        self,
        cleaned_result,
        execution_time,
        continuous=False,
    ):
        print()
        print("=" * 60)
        if continuous:
            print("     CONTINUOUS ENERGY MEASUREMENT COMPLETE")
        else:
            print("           ENERGY MEASUREMENT COMPLETE")
        print("=" * 60)
        print(
            "Energy Consumed:",
            cleaned_result.get("energy_consumed"),
            "kWh",
        )
        print(
            "Emissions:",
            cleaned_result.get("emissions"),
            "kg CO2eq",
        )
        print("Execution Time:", execution_time, "seconds")
        print(
            "Return Code:",
            cleaned_result.get("return_code"),
        )
        if cleaned_result.get("stop_reason"):
            print(
                "Stop Reason:",
                cleaned_result["stop_reason"],
            )
        print("=" * 60)
