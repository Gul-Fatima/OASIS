from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from modules.energy_estimation.project import Project
from modules.energy_estimation.executor import ProjectExecutor
from modules.energy_estimation.estimator import EnergyEstimator
from modules.code_understanding.parser import parse_code


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="OASIS Energy Estimation API",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]

)


# ============================================================
# REQUEST MODEL
# ============================================================

class EnergyRequest(BaseModel):

    project_path: str

    command: str

    timeout: int = 300


class CodeAnalysisRequest(BaseModel):

    file_path: str

    language: str = "python"


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {

        "application": "OASIS",

        "module": "Energy Estimation",

        "status": "running"

    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():

    return {

        "status": "healthy"

    }


# ============================================================
# ENERGY ESTIMATION
# ============================================================

@app.post("/api/energy/estimate")
def estimate_energy(
    request: EnergyRequest
):

    try:

        print()
        print("=" * 70)
        print("                 OASIS API REQUEST")
        print("=" * 70)

        print(
            f"Project Path : {request.project_path}"
        )

        print(
            f"Command      : {request.command}"
        )

        print(
            f"Timeout      : {request.timeout}"
        )


        # ----------------------------------------------------
        # 1. LOAD PROJECT
        # ----------------------------------------------------

        project = Project(
            request.project_path
        )


        # ----------------------------------------------------
        # 2. CREATE EXECUTOR
        # ----------------------------------------------------

        executor = ProjectExecutor(

            command=request.command,

            working_directory=str(
                project.project_path
            ),

            timeout=request.timeout

        )


        # ----------------------------------------------------
        # 3. CREATE ENERGY ESTIMATOR
        # ----------------------------------------------------

        estimator = EnergyEstimator(

            output_dir="results"

        )


        # ----------------------------------------------------
        # 4. EXECUTE PROJECT + CODECARBON
        # ----------------------------------------------------

        result = estimator.estimate(
            executor
        )


        # ----------------------------------------------------
        # 5. ADD PROJECT INFORMATION
        # ----------------------------------------------------

        result[
            "project_path"
        ] = str(
            project.project_path
        )

        result[
            "file_count"
        ] = project.get_file_count()


        # ----------------------------------------------------
        # 6. RETURN ACTUAL CODECARBON DATA
        # ----------------------------------------------------

        print()
        print(
            "Returning CodeCarbon measurement "
            "to frontend..."
        )

        print("=" * 70)


        return result


    except FileNotFoundError as e:

        raise HTTPException(

            status_code=404,

            detail=str(e)

        )


    except ValueError as e:

        raise HTTPException(

            status_code=400,

            detail=str(e)

        )


    except Exception as e:

        print()
        print(
            "OASIS BACKEND ERROR:",
            str(e)
        )

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )


# ============================================================
# CODE UNDERSTANDING
# ============================================================

@app.post("/api/code/analyze")
def analyze_code(
    request: CodeAnalysisRequest
):

    try:

        print()
        print("=" * 70)
        print("           CODE UNDERSTANDING REQUEST")
        print("=" * 70)

        print(
            f"File Path  : {request.file_path}"
        )

        print(
            f"Language   : {request.language}"
        )


        # ----------------------------------------------------
        # 1. READ FILE
        # ----------------------------------------------------

        file_path = Path(
            request.file_path
        )

        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {request.file_path}"
            )

        source = file_path.read_text(
            encoding="utf-8"
        )


        # ----------------------------------------------------
        # 2. PARSE CODE
        # ----------------------------------------------------

        state = parse_code(
            source,
            path=str(file_path),
            language=request.language
        )


        # ----------------------------------------------------
        # 3. RETURN STRUCTURED RESULT
        # ----------------------------------------------------

        result = state.to_dict()

        result["file_size"] = len(
            source.encode("utf-8")
        )

        result["line_count"] = len(
            source.splitlines()
        )

        print()
        print(
            f"Parsed: {len(state.functions)} functions, "
            f"{len(state.classes)} classes, "
            f"{len(state.loops)} loops"
        )

        print("=" * 70)


        return result


    except FileNotFoundError as e:

        raise HTTPException(

            status_code=404,

            detail=str(e)
        )

    except ValueError as e:

        raise HTTPException(

            status_code=400,

            detail=str(e)
        )

    except Exception as e:

        print()
        print(
            "OASIS BACKEND ERROR:",
            str(e)
        )

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )