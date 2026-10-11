from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "PROJECT_CODE_CONTEXT.md"

INCLUDE_DIRS = ("src", "scripts", "tests", "configs", "hummingbot_ext", "docs")
ROOT_FILES = (
    "README.md",
    "PROJECT_PLAN.md",
    "CURRENT_SETUP_AND_PROGRESS.md",
    "pyproject.toml",
    ".gitignore",
)

# These directories are included as layout only.
LAYOUT_DIRS = ("data", "reports", "local_snapshots")

EXTENSIONS = {".py", ".md", ".toml", ".yaml", ".yml", ".sh", ".ini"}
EXCLUDED_ROOTS = {".venv", ".git", "data", "reports", "local_snapshots", "logs", ".pytest_cache"}
EXCLUDED_PARTS = {"__pycache__"}


def allowed(path: Path) -> bool:
    relative = path.relative_to(ROOT)

    if relative.parts[0] in EXCLUDED_ROOTS:
        return False

    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False

    if path.name.startswith(".env"):
        return False

    name = path.name.lower()
    if "credential" in name or "secret" in name:
        return False

    return path.suffix in EXTENSIONS


def language(path: Path) -> str:
    return {
        ".py": "python",
        ".md": "markdown",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".sh": "bash",
        ".ini": "ini",
    }.get(path.suffix, "")


def human_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{size} B"


def directory_size(path: Path) -> int:
    total = 0

    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass

    return total


def export_layout(out, directory_name: str):
    base = ROOT / directory_name

    out.write(f"\n## `{directory_name}/` Layout\n\n")

    if not base.exists():
        out.write("_Directory does not exist._\n")
        return

    directories = sorted(
        (p for p in base.rglob("*") if p.is_dir()),
        key=lambda p: str(p.relative_to(ROOT)),
    )

    files = sorted(
        (p for p in base.rglob("*") if p.is_file()),
        key=lambda p: str(p.relative_to(ROOT)),
    )

    out.write(
        f"- Directories: {len(directories)}\n"
        f"- Files: {len(files)}\n"
        f"- Total size: {human_size(directory_size(base))}\n\n"
    )

    out.write("```text\n")
    out.write(f"{directory_name}/\n")

    for path in directories:
        relative = path.relative_to(ROOT)
        out.write(f"DIR  {relative}/\n")

    for path in files:
        relative = path.relative_to(ROOT)

        try:
            size = human_size(path.stat().st_size)
        except OSError:
            size = "unknown"

        out.write(f"FILE {relative} [{size}]\n")

    out.write("```\n")


def main():
    files = []

    for name in ROOT_FILES:
        path = ROOT / name
        if path.exists():
            files.append(path)

    for directory in INCLUDE_DIRS:
        base = ROOT / directory

        if not base.exists():
            continue

        files.extend(
            path
            for path in base.rglob("*")
            if path.is_file() and allowed(path)
        )

    files = sorted(
        set(files),
        key=lambda path: str(path.relative_to(ROOT)),
    )

    with OUTPUT.open("w") as out:
        out.write("# Hyperliquid Microstructure Bot — Project Context\n\n")
        out.write("Automatically generated repository snapshot.\n\n")

        out.write("## Source Files\n\n")

        for path in files:
            out.write(f"- `{path.relative_to(ROOT)}`\n")

        out.write("\n# Local Data and Report Layout\n")

        for directory in LAYOUT_DIRS:
            export_layout(out, directory)

        out.write("\n# Source Contents\n")

        for path in files:
            try:
                content = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue

            out.write(
                f"\n---\n\n"
                f"## `{path.relative_to(ROOT)}`\n\n"
                f"```{language(path)}\n"
                f"{content.rstrip()}\n"
                f"```\n"
            )

    print(f"Exported {len(files)} source files to {OUTPUT}")

    for directory in LAYOUT_DIRS:
        base = ROOT / directory
        if base.exists():
            file_count = sum(1 for path in base.rglob("*") if path.is_file())
            print(
                f"{directory}/: "
                f"{file_count} files, "
                f"{human_size(directory_size(base))}"
            )


if __name__ == "__main__":
    main()