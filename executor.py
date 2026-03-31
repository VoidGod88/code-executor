import json
import sys
import traceback
from io import StringIO
import time

def safe_exec_code(code: str, timeout: int = 30):
    """Safely execute student code and catch syntax/runtime errors"""
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    namespace = {}
    captured_stdout = ""
    start_time = time.time()

    try:
        exec(code, namespace)
        success = True
        error = ""
        details = ""
    except Exception as e:
        success = False
        error = f"Code execution error: {type(e).__name__}: {str(e)}"
        details = traceback.format_exc()
    finally:
        captured_stdout = sys.stdout.getvalue()
        sys.stdout = old_stdout

    exec_time = time.time() - start_time
    return {
        "success": success,
        "namespace": namespace,
        "stdout": captured_stdout,
        "error": error,
        "details": details,
        "execution_time": round(exec_time, 3)
    }


def run_python_tests(namespace: dict, tests: list, captured_stdout: str = ""):
    """Run all test cases against the executed code"""
    results = []
    all_passed = True

    for idx, test in enumerate(tests):
        func_name = test.get("function")
        inputs = test.get("input", [])
        expected = test.get("expected")
        description = test.get("description", f"Test case {idx+1}")

        if func_name not in namespace:
            all_passed = False
            results.append({
                "passed": False,
                "description": description,
                "error": f"Function '{func_name}' is not defined",
                "input": inputs,
                "expected": expected
            })
            continue

        try:
            func = namespace[func_name]
            if isinstance(inputs, list):
                actual = func(*inputs)
            else:
                actual = func(inputs)

            if actual == expected:
                results.append({
                    "passed": True,
                    "description": description,
                    "input": inputs,
                    "expected": expected,
                    "actual": actual
                })
            else:
                all_passed = False
                results.append({
                    "passed": False,
                    "description": description,
                    "input": inputs,
                    "expected": expected,
                    "actual": actual,
                    "error": f"Expected {expected}, got {actual}"
                })
        except Exception as e:
            all_passed = False
            results.append({
                "passed": False,
                "description": description,
                "input": inputs,
                "expected": expected,
                "error": f"Runtime error: {type(e).__name__}: {str(e)}"
            })

    total = len(results)
    passed_count = sum(1 for r in results if r.get("passed", False))

    return {
        "passed": all_passed,
        "error": "" if all_passed else f"Passed {passed_count}/{total} test cases",
        "details": json.dumps(results, ensure_ascii=False, indent=2),
        "stdout": captured_stdout
    }