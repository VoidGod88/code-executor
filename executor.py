import json
import sys
import traceback
from io import StringIO
import time
import re

def safe_exec_code(code: str, timeout: int = 30):
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

def parse_test_cases(test_cases):
    if not test_cases or not isinstance(test_cases, str):
        return {"success": False, "error": "Test cases are empty or not string"}

    cleaned = test_cases.strip()
    start = cleaned.find('```')
    if start != -1:
        first_line_end = cleaned.find('\n', start)
        if first_line_end == -1:
            first_line_end = start + 3
        end = cleaned.rfind('```')
        if end != -1 and end > first_line_end:
            cleaned = cleaned[first_line_end:end].strip()

    if not cleaned:
        return {"success": False, "error": "No JSON content found after cleaning"}

    try:
        tests = json.loads(cleaned)
        if not isinstance(tests, list):
            tests = [tests] if tests else []
        return {"success": True, "tests": tests}
    except json.JSONDecodeError as e:
        preview = cleaned[:200] + ("..." if len(cleaned) > 200 else "")
        return {
            "success": False,
            "error": f"JSON decode error: {str(e)}. Cleaned content preview: {preview}"
        }
    except Exception as e:
        return {"success": False, "error": f"Parse error: {str(e)}"}

def run_python_tests(namespace: dict, tests: list, captured_stdout: str = ""):
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