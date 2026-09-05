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

    project = Project(project_path)

    executor = ProjectExecutor(
        command=command,
        working_directory=project_path
    )

    estimator = EnergyEstimator()

    result = estimator.estimate(executor)

    EnergyReport.display(
        project,
        result
    )


if __name__ == "__main__":
    main()