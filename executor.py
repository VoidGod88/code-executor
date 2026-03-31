import json
import sys
import traceback
from io import StringIO
import time
import inspect
import ast

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

    # 尝试 JSON 解析
    try:
        tests = json.loads(cleaned)
    except json.JSONDecodeError as json_err:
        # 回退到 Python 字面量解析（支持 None, True, False）
        try:
            tests = ast.literal_eval(cleaned)
        except (ValueError, SyntaxError) as literal_err:
            preview = cleaned[:200] + ("..." if len(cleaned) > 200 else "")
            return {
                "success": False,
                "error": f"Failed to parse test cases as JSON or Python literal. "
                         f"JSON error: {str(json_err)}; Literal error: {str(literal_err)}. "
                         f"Content preview: {preview}"
            }

    if not isinstance(tests, list):
        tests = [tests] if tests else []
    return {"success": True, "tests": tests}


def _has_pandas():
    try:
        import pandas as pd
        return pd
    except ImportError:
        return None


def _normalize_actual(actual):
    pd = _has_pandas()
    if pd is None:
        return actual

    if isinstance(actual, pd.DataFrame):
        return actual.to_dict('list')
    if isinstance(actual, pd.Series):
        return actual.to_list()
    if hasattr(actual, 'dtype') and hasattr(actual, 'item'):
        try:
            return actual.item()
        except:
            pass
    if actual is None or (isinstance(actual, float) and actual != actual):
        return None
    return actual


def _normalize_expected(expected):
    if isinstance(expected, str) and expected.lower() == 'nan':
        return None
    return expected


def _deep_equal(a, b):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False

    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        for key in a:
            if not _deep_equal(a[key], b[key]):
                return False
        return True
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        for ai, bi in zip(a, b):
            if not _deep_equal(ai, bi):
                return False
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a != a and b != b:  # both NaN
            return True
        if a != a or b != b:   # only one NaN
            return False
        return abs(a - b) < 1e-9
    return a == b


def _make_json_serializable(obj):
    pd = _has_pandas()
    if pd is not None:
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict('list')
        if isinstance(obj, pd.Series):
            return obj.to_list()
    if hasattr(obj, 'dtype') and hasattr(obj, 'item'):
        try:
            return obj.item()
        except:
            pass
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(v) for v in obj]
    if isinstance(obj, float) and obj != obj:
        return None
    return obj


def run_python_tests(namespace: dict, tests: list, captured_stdout: str = ""):
    results = []
    all_passed = True

    for idx, test in enumerate(tests):
        func_name = test.get("function")
        inputs = test.get("input", [])
        expected = _normalize_expected(test.get("expected"))
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

        func = namespace[func_name]

        # 不再自动转换输入，直接使用原始 inputs
        # 调用函数
        try:
            # 根据 inputs 的类型决定如何传参
            if isinstance(inputs, list):
                # 如果列表非空，用 *inputs 展开；否则直接调用函数（无参数）
                if len(inputs) > 0:
                    actual = func(*inputs)
                else:
                    actual = func()
            else:
                # 非列表，直接传入单个参数
                actual = func(inputs)

            actual_norm = _normalize_actual(actual)
            expected_norm = _normalize_expected(expected)

            if _deep_equal(actual_norm, expected_norm):
                results.append({
                    "passed": True,
                    "description": description,
                    "input": inputs,
                    "expected": expected,
                    "actual": actual_norm
                })
            else:
                all_passed = False
                results.append({
                    "passed": False,
                    "description": description,
                    "input": inputs,
                    "expected": expected,
                    "actual": actual_norm,
                    "error": f"Expected {expected}, got {actual_norm}"
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

    serializable_results = _make_json_serializable(results)

    return {
        "passed": all_passed,
        "error": "" if all_passed else f"Passed {passed_count}/{total} test cases",
        "details": json.dumps(serializable_results, ensure_ascii=False, indent=2),
        "stdout": captured_stdout
    }