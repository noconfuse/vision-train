"""约束上下文之间的依赖方向：跨域只能经由 application 层门面。"""

import ast
import os
import unittest
from importlib.util import find_spec

CONTEXTS_ROOT = os.path.abspath(next(iter(find_spec("contexts").submodule_search_locations)))
PROTOCOLS_ROOT = os.path.abspath(next(iter(find_spec("protocols").submodule_search_locations)))
WEB_ROOT = os.path.dirname(CONTEXTS_ROOT)


def _iter_python_files(root):
    for dirpath, _, files in os.walk(root):
        if "__pycache__" in dirpath:
            continue
        for filename in files:
            if filename.endswith(".py"):
                yield os.path.join(dirpath, filename)


def _iter_imported_modules(path):
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            yield node.lineno, node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name


def _resolve_domain(path):
    relative = os.path.relpath(path, CONTEXTS_ROOT)
    parts = relative.split(os.sep)
    if len(parts) < 2:
        return None
    return parts[0]


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_cross_domain_imports_go_through_application_layer(self):
        violations = []
        for path in _iter_python_files(CONTEXTS_ROOT):
            domain = _resolve_domain(path)
            if not domain:
                continue
            for lineno, module in _iter_imported_modules(path):
                if not module.startswith("contexts."):
                    continue
                target = module.split(".")[1]
                if target == domain:
                    continue
                if module == f"contexts.{target}":
                    continue
                if module.startswith(f"contexts.{target}.application"):
                    continue
                violations.append(
                    f"{os.path.relpath(path, WEB_ROOT)}:{lineno} -> {module}"
                )
        self.assertEqual([], violations, "跨域依赖必须走对方 application 层：\n" + "\n".join(violations))

    def test_protocols_do_not_depend_on_contexts(self):
        violations = []
        for path in _iter_python_files(PROTOCOLS_ROOT):
            for lineno, module in _iter_imported_modules(path):
                if module.startswith("contexts."):
                    violations.append(
                        f"{os.path.relpath(path, WEB_ROOT)}:{lineno} -> {module}"
                    )
        self.assertEqual([], violations, "protocols 必须是纯契约，不能反向依赖 contexts：\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
