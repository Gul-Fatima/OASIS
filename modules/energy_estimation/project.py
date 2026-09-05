from pathlib import Path


class Project:

    def __init__(self, project_path: str):

        self.project_path = Path(project_path)

        if not self.project_path.exists():
            raise FileNotFoundError(
                f"Project not found: {project_path}"
            )

        if not self.project_path.is_dir():
            raise ValueError(
                "Project path must be a directory"
            )

    def get_files(self):

        return [
            file
            for file in self.project_path.rglob("*")
            if file.is_file()
        ]

    def get_file_count(self):

        return len(self.get_files())