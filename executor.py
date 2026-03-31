import json
import sys
import traceback
from io import StringIO
import time
import inspect
from typing import Any, List, Dict, Union


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


# --------------------------------------------------------------
# 辅助函数：处理 pandas 数据类型
# --------------------------------------------------------------
def _has_pandas():
    try:
        import pandas as pd
        return pd
    except ImportError:
        return None


def _to_dataframe(data):
    """将各种输入转换为 pandas DataFrame"""
    pd = _has_pandas()
    if pd is None:
        return data  # 无 pandas 时原样返回

    # 已经是 DataFrame
    if isinstance(data, pd.DataFrame):
        return data

    # 处理空列表 -> 空 DataFrame
    if data == []:
        return pd.DataFrame()

    # 处理单个字典（可能是一行记录）
    if isinstance(data, dict):
        # 如果字典的值也都是字典，说明是行式结构（如 {id1: {age:..}, id2: {...}}）
        if all(isinstance(v, dict) for v in data.values()):
            # 将每个内部字典作为一行，收集所有行
            rows = list(data.values())
            return pd.DataFrame(rows)
        # 否则尝试常规列式转换
        try:
            return pd.DataFrame(data)
        except ValueError:
            # 如果遇到标量值错误，说明是行式字典（如 {"age":25,"name":"Charlie"}）
            # 将其包装成列表再转换
            return pd.DataFrame([data])

    # 处理列表
    if isinstance(data, list):
        # 如果列表元素是字典，将其作为行记录
        if all(isinstance(item, dict) for item in data):
            return pd.DataFrame(data)
        # 如果是标量列表，作为单列 DataFrame
        try:
            return pd.DataFrame(data)
        except:
            return data

    return data


def _normalize_actual(actual):
    """将实际返回值转换为可 JSON 序列化且易于比较的形式"""
    pd = _has_pandas()
    if pd is None:
        return actual

    # 处理 pandas 对象
    if isinstance(actual, pd.DataFrame):
        return actual.to_dict('list')  # 列式字典，与测试用例常见格式一致
    if isinstance(actual, pd.Series):
        return actual.to_list()
    # 处理 numpy 标量
    if hasattr(actual, 'dtype') and hasattr(actual, 'item'):
        # numpy 整数/浮点数
        try:
            return actual.item()
        except:
            pass
    # 处理 NaN / None
    if actual is None or (isinstance(actual, float) and actual != actual):  # NaN 检查
        return None
    return actual


def _normalize_expected(expected):
    """将预期值统一转换为可比较的格式"""
    # 如果预期是字符串 'nan'，视为 None（与 pandas 的 NaN 比较时视为相等）
    if isinstance(expected, str) and expected.lower() == 'nan':
        return None
    return expected


def _deep_equal(a, b):
    """深度比较两个对象，支持 pandas DataFrame 和 NaN"""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False

    # 处理 DataFrame 字典比较
    if isinstance(a, dict) and isinstance(b, dict):
        # 如果键和值列表长度相同，且所有值近似相等
        if set(a.keys()) != set(b.keys()):
            return False
        for key in a:
            if not _deep_equal(a[key], b[key]):
                return False
        return True
    # 处理列表比较
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        for ai, bi in zip(a, b):
            if not _deep_equal(ai, bi):
                return False
        return True
    # 数字比较（允许微小误差）
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        # 处理 NaN
        if a != a and b != b:  # 都是 NaN
            return True
        if a != a or b != b:   # 只有一个 NaN
            return False
        # 允许 1e-9 误差
        return abs(a - b) < 1e-9
    # 其他直接比较
    return a == b


# --------------------------------------------------------------
# 辅助函数：递归转换不可 JSON 序列化的对象
# --------------------------------------------------------------
def _make_json_serializable(obj):
    """递归地将对象转换为 JSON 可序列化的形式"""
    pd = _has_pandas()
    # 处理 pandas 对象
    if pd is not None:
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict('list')
        if isinstance(obj, pd.Series):
            return obj.to_list()
    # 处理 numpy 标量
    if hasattr(obj, 'dtype') and hasattr(obj, 'item'):
        try:
            return obj.item()
        except:
            pass
    # 处理字典
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    # 处理列表/元组
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(v) for v in obj]
    # 处理 NaN
    if isinstance(obj, float) and obj != obj:  # NaN 检查
        return None
    return obj


# --------------------------------------------------------------
# 核心测试函数
# --------------------------------------------------------------
def run_python_tests(namespace: dict, tests: list, captured_stdout: str = ""):
    results = []
    all_passed = True

    for idx, test in enumerate(tests):
        func_name = test.get("function")
        inputs = test.get("input", [])
        expected = _normalize_expected(test.get("expected"))
        description = test.get("description", f"Test case {idx+1}")

        # 检查函数是否存在
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

        # 智能预处理输入：根据函数参数个数自动转换
        try:
            # 获取函数期望的参数个数
            sig = inspect.signature(func)
            param_count = len(sig.parameters)

            # 如果函数期望 1 个参数，我们尝试将 inputs 转换为合适的 DataFrame
            if param_count == 1:
                # 使用增强的 _to_dataframe 统一处理
                inputs = _to_dataframe(inputs)

            # 如果函数期望多个参数且 inputs 是列表，保持原样
            # 注意：对于空列表，我们也会保持列表，但调用时会特殊处理

        except Exception as e:
            # 预处理异常，记录为测试失败
            all_passed = False
            results.append({
                "passed": False,
                "description": description,
                "input": inputs,
                "expected": expected,
                "error": f"Test preprocessing error: {type(e).__name__}: {str(e)}"
            })
            continue

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

            # 规范化实际输出
            actual_norm = _normalize_actual(actual)
            expected_norm = _normalize_expected(expected)

            # 深度比较
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

    # 将 results 转换为完全可序列化的形式
    serializable_results = _make_json_serializable(results)

    return {
        "passed": all_passed,
        "error": "" if all_passed else f"Passed {passed_count}/{total} test cases",
        "details": json.dumps(serializable_results, ensure_ascii=False, indent=2),
        "stdout": captured_stdout
    }