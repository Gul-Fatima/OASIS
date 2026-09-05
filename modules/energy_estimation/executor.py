import os
import subprocess


class ProjectExecutor:

    def __init__(
        self,
        command: str,
        working_directory: str,
        timeout: int = 300
    ):

        self.command = command

        self.working_directory = (
            working_directory
        )

        self.timeout = timeout


    def execute(self):

        print()
        print("=" * 60)
        print("           STARTING PROJECT")
        print("=" * 60)

        print(
            f"Working Directory : "
            f"{self.working_directory}"
        )

        print(
            f"Command           : "
            f"{self.command}"
        )


        # ----------------------------------------------------
        # ENVIRONMENT
        # ----------------------------------------------------

        environment = os.environ.copy()

        environment[
            "PYTHONIOENCODING"
        ] = "utf-8"

        environment[
            "PYTHONUTF8"
        ] = "1"


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

                timeout=self.timeout

            )


            print(
                f"Return Code : "
                f"{result.returncode}"
            )


            return {

                "return_code":
                    result.returncode,

                "stdout":
                    result.stdout,

                "stderr":
                    result.stderr

            }


        except subprocess.TimeoutExpired:

            return {

                "return_code": -1,

                "stdout": "",

                "stderr":
                    "Project execution timed out."

            }


        except Exception as e:

            return {

                "return_code": -1,

                "stdout": "",

                "stderr": str(e)

            }