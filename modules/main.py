from energy_estimation.project import Project
from energy_estimation.executor import ProjectExecutor
from energy_estimation.estimator import EnergyEstimator
from energy_estimation.report import EnergyReport


def main():

    project_path = input(
        "Enter project path: "
    ).strip()

    command = input(
        "Enter execution command: "
    ).strip()

    continuous_raw = input(
        "Continuous mode for infinite process "
        "(PHP/server)? [y/N]: "
    ).strip().lower()

    continuous = continuous_raw in (
        "y",
        "yes",
        "1",
        "true",
    )

    timeout_raw = input(
        "Monitor duration / timeout in seconds "
        "[300]: "
    ).strip()

    timeout = int(timeout_raw) if timeout_raw else 300

    project = Project(project_path)

    executor = ProjectExecutor(
        command=command,
        working_directory=project_path,
        timeout=timeout,
    )

    estimator = EnergyEstimator()

    if continuous:
        interval_raw = input(
            "Flush interval in seconds [10]: "
        ).strip()
        interval = int(interval_raw) if interval_raw else 10

        last = None
        for snapshot in estimator.estimate_continuous(
            executor,
            interval_seconds=interval,
            duration_seconds=timeout,
        ):
            last = snapshot
            print(
                f"[snapshot {snapshot['snapshot_index']}] "
                f"energy={snapshot.get('energy_consumed')} kWh "
                f"final={snapshot.get('final')}"
            )

        if last is not None:
            EnergyReport.display(project, last)
    else:
        result = estimator.estimate(executor)
        EnergyReport.display(project, result)


if __name__ == "__main__":
    main()
