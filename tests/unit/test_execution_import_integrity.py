import ast
from pathlib import Path


def test_execution_modules_do_not_import_missing_hlbot_modules():
    package_dir = Path(__file__).resolve().parents[2] / "src" / "hlbot"
    execution_dir = package_dir / "execution"
    assert execution_dir.is_dir()
    checked = 0
    for module_path in execution_dir.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            candidates = []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                candidates.append(node.module)
            elif isinstance(node, ast.Import):
                candidates.extend(alias.name for alias in node.names)
            for module in candidates:
                if not module.startswith("hlbot."):
                    continue
                relative = module.split(".")[1:]
                target = package_dir.joinpath(*relative)
                checked += 1
                assert target.with_suffix(".py").is_file() or (
                    target / "__init__.py"
                ).is_file(), f"{module_path}: missing internal module {module}"
    assert checked > 0
