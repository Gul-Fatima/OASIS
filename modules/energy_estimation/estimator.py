import os
import time
import pandas as pd

from codecarbon import EmissionsTracker


class EnergyEstimator:

    def __init__(self, output_dir="results"):

        self.output_dir = os.path.abspath(output_dir)

        os.makedirs(
            self.output_dir,
            exist_ok=True
        )

        self.emissions_file = os.path.join(
            self.output_dir,
            "emissions.csv"
        )


    def estimate(self, executor):

        print()
        print("=" * 60)
        print("           STARTING ENERGY MEASUREMENT")
        print("=" * 60)

        # ----------------------------------------------------
        # Remember existing file state
        # ----------------------------------------------------

        previous_timestamp = None

        if os.path.exists(self.emissions_file):

            try:

                old_df = pd.read_csv(
                    self.emissions_file
                )

                if not old_df.empty:

                    previous_timestamp = (
                        old_df.iloc[-1].get(
                            "timestamp"
                        )
                    )

            except Exception:
                pass


        # ----------------------------------------------------
        # START CODECARBON
        # ----------------------------------------------------

        tracker = EmissionsTracker(

            project_name="OASIS",

            output_dir=self.output_dir,

            save_to_file=True,

            log_level="error"

        )


        start_time = time.perf_counter()

        execution_result = None


        try:

            tracker.start()

            # ------------------------------------------------
            # EXECUTE COMPLETE PROJECT
            # ------------------------------------------------

            execution_result = executor.execute()


        finally:

            # ------------------------------------------------
            # STOP CODECARBON
            # ------------------------------------------------

            tracker.stop()


        end_time = time.perf_counter()


        execution_time = (
            end_time - start_time
        )


        # ----------------------------------------------------
        # READ ACTUAL CODECARBON RESULT
        # ----------------------------------------------------

        if not os.path.exists(
            self.emissions_file
        ):

            raise RuntimeError(
                "CodeCarbon did not create "
                "emissions.csv"
            )


        try:

            df = pd.read_csv(
                self.emissions_file
            )

        except Exception as e:

            raise RuntimeError(
                f"Could not read CodeCarbon "
                f"emissions.csv: {e}"
            )


        if df.empty:

            raise RuntimeError(
                "CodeCarbon emissions.csv "
                "is empty."
            )


        # ----------------------------------------------------
        # GET LATEST MEASUREMENT
        # ----------------------------------------------------

        latest = df.iloc[-1].to_dict()


        # ----------------------------------------------------
        # CONVERT NUMPY VALUES TO PYTHON VALUES
        # ----------------------------------------------------

        cleaned_result = {}

        for key, value in latest.items():

            if pd.isna(value):

                cleaned_result[key] = None

            else:

                # Convert numpy numeric values
                # into normal Python values.

                if hasattr(value, "item"):

                    value = value.item()

                cleaned_result[key] = value


        # ----------------------------------------------------
        # ADD OASIS EXECUTION INFORMATION
        # ----------------------------------------------------

        cleaned_result[
            "execution_time_seconds"
        ] = execution_time

        cleaned_result[
            "return_code"
        ] = execution_result["return_code"]

        cleaned_result[
            "stdout"
        ] = execution_result["stdout"]

        cleaned_result[
            "stderr"
        ] = execution_result["stderr"]


        # ----------------------------------------------------
        # EXECUTION STATUS
        # ----------------------------------------------------

        if execution_result["return_code"] == 0:

            cleaned_result[
                "execution_status"
            ] = "success"

            cleaned_result[
                "baseline_valid"
            ] = True

        else:

            cleaned_result[
                "execution_status"
            ] = "failed"

            cleaned_result[
                "baseline_valid"
            ] = False


        print()
        print("=" * 60)
        print("           ENERGY MEASUREMENT COMPLETE")
        print("=" * 60)

        print(
            "Energy Consumed:",
            cleaned_result.get(
                "energy_consumed"
            ),
            "kWh"
        )

        print(
            "Emissions:",
            cleaned_result.get(
                "emissions"
            ),
            "kg CO2eq"
        )

        print(
            "Execution Time:",
            execution_time,
            "seconds"
        )

        print(
            "Return Code:",
            execution_result[
                "return_code"
            ]
        )

        print("=" * 60)


        return cleaned_result