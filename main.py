from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json
from executor import safe_exec_code, run_python_tests

app = FastAPI(
    title="ML Code Executor",
    description="Safe execution service for AI, Data Analysis & Machine Learning code"
)

class ExecuteRequest(BaseModel):
    code: str
    test_cases: str = "[]"
    language: str = "python"
    timeout: int = 30

@app.post("/execute")
async def execute_code(request: ExecuteRequest):
    if request.language.lower() != "python":
        raise HTTPException(status_code=400, detail="Only Python is supported")

    if len(request.code) > 100000:
        raise HTTPException(status_code=400, detail="Code is too long")

    # Execute the code first
    exec_result = safe_exec_code(request.code, request.timeout)

    if not exec_result["success"]:
        return {
            "passed": False,
            "error": exec_result["error"],
            "details": exec_result["details"],
            "stdout": exec_result["stdout"],
            "execution_time": exec_result["execution_time"]
        }

    # Parse test cases
    try:
        tests = json.loads(request.test_cases) if isinstance(request.test_cases, str) else request.test_cases
        if not isinstance(tests, list):
            tests = [tests] if tests else []
    except Exception as e:
        return {
            "passed": False,
            "error": "Invalid test cases JSON format",
            "details": str(e),
            "stdout": exec_result["stdout"]
        }

    # Run tests
    test_result = run_python_tests(exec_result["namespace"], tests, exec_result["stdout"])

    return {
        "passed": test_result["passed"],
        "error": test_result["error"],
        "details": test_result["details"],
        "stdout": test_result["stdout"],
        "execution_time": exec_result["execution_time"]
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}