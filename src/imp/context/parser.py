"""Context parser — L2 AST extraction.

L1 constraint: Only import from imp.context.models, stdlib, tree-sitter (optional).
NO imports from other L1/L2 modules.
"""

import ast
from pathlib import Path

from imp.context.models import (
    ClassInfo,
    DirectoryModule,
    FileInfo,
    FunctionInfo,
    ImportInfo,
    Language,
    ModuleInfo,
    ProjectScan,
)

# Optional tree-sitter support
try:
    import tree_sitter  # type: ignore[import-not-found]

    TREE_SITTER_AVAILABLE = True  # pragma: no cover
except ImportError:
    tree_sitter = None
    TREE_SITTER_AVAILABLE = False


def parse_python(path: str, source: str) -> ModuleInfo:
    """Parse Python source using stdlib ast module.

    Returns ModuleInfo with functions, classes, imports extracted.
    On SyntaxError: returns ModuleInfo with parse_error set.

    Args:
        path: File path for context
        source: Python source code

    Returns:
        ModuleInfo with AST data or parse_error
    """
    # Create FileInfo
    file_info = FileInfo(
        path=path,
        size_bytes=len(source.encode()),
        language=Language.PYTHON,
        line_count=source.count("\n") + (1 if source and not source.endswith("\n") else 0),
    )

    # Parse AST
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return ModuleInfo(
            file_info=file_info,
            parse_error=f"SyntaxError: {e.msg} at line {e.lineno}",
        )
    except IndentationError as e:  # pragma: no cover — IndentationError is subclass of SyntaxError
        return ModuleInfo(
            file_info=file_info,
            parse_error=f"IndentationError: {e.msg} at line {e.lineno}",
        )

    # Extract module-level entities
    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []
    imports: list[ImportInfo] = []
    exports: list[str] = []
    module_docstring = ast.get_docstring(tree)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_extract_function(node, is_method=False))

        elif isinstance(node, ast.ClassDef):
            classes.append(_extract_class(node))

        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportInfo(
                        module=alias.name,
                        names=[],
                        is_from_import=False,
                    )
                )

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""  # Relative imports have module=None
            names = [alias.name for alias in node.names]
            imports.append(
                ImportInfo(
                    module=module,
                    names=names,
                    is_from_import=True,
                )
            )

        elif isinstance(node, ast.Assign):
            # Check for __all__
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    exports = _extract_exports(node.value)

    return ModuleInfo(
        file_info=file_info,
        functions=functions,
        classes=classes,
        imports=imports,
        module_docstring=module_docstring,
        exports=exports,
    )


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    is_method: bool,
) -> FunctionInfo:
    """Extract function info from AST node."""
    # Build signature
    signature_parts = [node.name, "("]

    args = node.args
    all_args = []

    # Regular args
    for i, arg in enumerate(args.args):
        arg_str = arg.arg
        if arg.annotation:
            arg_str += f": {ast.unparse(arg.annotation)}"
        # Check for defaults (they align with the end of args.args)
        default_offset = len(args.args) - len(args.defaults)
        if i >= default_offset:
            default_idx = i - default_offset
            arg_str += f" = {ast.unparse(args.defaults[default_idx])}"
        all_args.append(arg_str)

    # *args
    if args.vararg:
        vararg_str = f"*{args.vararg.arg}"
        if args.vararg.annotation:
            vararg_str += f": {ast.unparse(args.vararg.annotation)}"
        all_args.append(vararg_str)

    # **kwargs
    if args.kwarg:
        kwarg_str = f"**{args.kwarg.arg}"
        if args.kwarg.annotation:
            kwarg_str += f": {ast.unparse(args.kwarg.annotation)}"
        all_args.append(kwarg_str)

    signature_parts.append(", ".join(all_args))
    signature_parts.append(")")

    # Return annotation
    if node.returns:
        signature_parts.append(f" -> {ast.unparse(node.returns)}")

    signature = "".join(signature_parts)

    # Extract decorators
    decorators = []
    for decorator in node.decorator_list:
        try:
            decorators.append(ast.unparse(decorator))
        except Exception:  # pragma: no cover — ast.unparse doesn't fail in Python 3.12+
            if isinstance(decorator, ast.Name):
                decorators.append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                decorators.append(decorator.attr)

    return FunctionInfo(
        name=node.name,
        signature=signature,
        line_number=node.lineno,
        docstring=ast.get_docstring(node),
        is_method=is_method,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        decorators=decorators,
    )


def _extract_class(node: ast.ClassDef) -> ClassInfo:
    """Extract class info from AST node."""
    # Extract bases
    bases = []
    for base in node.bases:
        try:
            bases.append(ast.unparse(base))
        except Exception:  # pragma: no cover — ast.unparse doesn't fail in Python 3.12+
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)

    # Extract methods
    methods = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(_extract_function(child, is_method=True))

    return ClassInfo(
        name=node.name,
        line_number=node.lineno,
        docstring=ast.get_docstring(node),
        bases=bases,
        methods=methods,
    )


def _extract_exports(node: ast.expr) -> list[str]:
    """Extract __all__ list/tuple contents."""
    exports = []

    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                exports.append(elt.value)
            elif isinstance(
                elt, ast.Str
            ):  # pragma: no cover — Python 3.7 compat, not reachable on 3.12
                exports.append(str(elt.s))

    return exports


def parse_typescript(path: str, source: str) -> ModuleInfo:
    """Parse TypeScript/JavaScript source using tree-sitter.

    On ImportError (tree-sitter not installed): returns ModuleInfo
    with parse_error="tree-sitter not installed. Install with: pip install impx[tree-sitter]"

    Args:
        path: File path for context
        source: TypeScript/JavaScript source code

    Returns:
        ModuleInfo with AST data or parse_error
    """
    # Determine language from extension
    if path.endswith(".ts") or path.endswith(".tsx"):
        language = Language.TYPESCRIPT
    else:
        language = Language.JAVASCRIPT

    # Create FileInfo
    file_info = FileInfo(
        path=path,
        size_bytes=len(source.encode()),
        language=language,
        line_count=source.count("\n") + (1 if source and not source.endswith("\n") else 0),
    )

    # Check if tree-sitter is available
    if not TREE_SITTER_AVAILABLE:
        return ModuleInfo(
            file_info=file_info,
            parse_error="tree-sitter not installed. Install with: pip install impx[tree-sitter]",
        )

    # TODO: Implement actual tree-sitter parsing
    # For v0.1, just return basic structure with graceful fallback
    return ModuleInfo(  # pragma: no cover — tree-sitter not installed in dev env
        file_info=file_info,
        parse_error="TypeScript parsing not yet implemented",
    )


def parse_file(path: str, source: str, language: Language) -> ModuleInfo:
    """Dispatcher: route to appropriate parser based on language.

    For UNKNOWN language: returns ModuleInfo with file_info only.

    Args:
        path: File path
        source: Source code
        language: Detected language

    Returns:
        ModuleInfo with AST data or minimal file_info for unknown languages
    """
    if language == Language.PYTHON:
        return parse_python(path, source)

    elif language in (Language.TYPESCRIPT, Language.JAVASCRIPT):
        return parse_typescript(path, source)

    else:  # UNKNOWN
        file_info = FileInfo(
            path=path,
            size_bytes=len(source.encode()),
            language=language,
            line_count=source.count("\n") + (1 if source and not source.endswith("\n") else 0),
        )
        return ModuleInfo(file_info=file_info)


def scan_and_parse(root: Path) -> ProjectScan:
    """Full L1+L2 scan. Calls scanner.scan_project() then enriches with parsing.

    Args:
        root: Project root directory

    Returns:
        ProjectScan with both L1 (file info) and L2 (AST data)
    """
    # Import scanner (may not be available yet during development)
    try:
        from imp.context.scanner import scan_project
    except ImportError as e:  # pragma: no cover — scanner always available in installed package
        raise ImportError(
            "Scanner not yet implemented. Import from imp.context.scanner failed."
        ) from e

    # Get L1 scan
    l1_scan = scan_project(root)

    # Enrich with L2 parsing
    enriched_modules = []

    for dir_module in l1_scan.modules:
        enriched_files = []

        for module_info in dir_module.files:
            file_path = Path(module_info.file_info.path)

            # Read file and parse
            try:
                source = file_path.read_text(encoding="utf-8")
                parsed = parse_file(
                    str(file_path),
                    source,
                    module_info.file_info.language,
                )
                enriched_files.append(parsed)
            except Exception as e:
                # If file read fails, keep original with error
                enriched_files.append(
                    ModuleInfo(
                        file_info=module_info.file_info,
                        parse_error=f"Failed to read file: {e}",
                    )
                )

        enriched_modules.append(
            DirectoryModule(
                path=dir_module.path,
                files=enriched_files,
                purpose=dir_module.purpose,
            )
        )

    # Count totals
    total_functions = sum(
        len(mod.functions) for dir_mod in enriched_modules for mod in dir_mod.files
    )
    total_classes = sum(len(mod.classes) for dir_mod in enriched_modules for mod in dir_mod.files)

    return ProjectScan(
        project_root=l1_scan.project_root,
        project_type=l1_scan.project_type,
        modules=enriched_modules,
        total_files=l1_scan.total_files,
        total_functions=total_functions,
        total_classes=total_classes,
        scanned_at=l1_scan.scanned_at,
    )
