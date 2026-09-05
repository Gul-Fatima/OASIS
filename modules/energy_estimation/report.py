class EnergyReport:

    @staticmethod
    def display(project, result):

        print()
        print("=" * 60)
        print("             OASIS ENERGY REPORT")
        print("=" * 60)

        print(f"Project           : {project.project_path}")
        print(f"Files             : {project.get_file_count()}")

        print("-" * 60)

        print(
            f"Energy Consumed   : "
            f"{result['energy_kwh']:.10f} kWh"
        )

        print(
            f"Execution Time    : "
            f"{result['execution_time_seconds']:.4f} seconds"
        )

        print(
            f"Return Code       : "
            f"{result['return_code']}"
        )

        print("-" * 60)

        if result["return_code"] == 0:
            print("Execution Status  : SUCCESS")
        else:
            print("Execution Status  : FAILED")

        print("-" * 60)

        # if result["stdout"]:
        #     print("\nPROJECT OUTPUT:")
        #     print(result["stdout"])

        if result["stderr"]:
            print("\nPROJECT ERROR:")
            print(result["stderr"])

        print("=" * 60)