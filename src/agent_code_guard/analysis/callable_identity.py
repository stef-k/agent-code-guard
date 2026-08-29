"""Language-specific callable identity and source-boundary normalization."""

from __future__ import annotations

from typing import Iterator

from .language_specs import CALLABLE_TYPES
from .regions import ExecutableRegion
from .syntax_nodes import node_text

__all__ = ["callable_identity", "is_anonymous_callable", "callable_source_start"]


def callable_identity(node, region: ExecutableRegion) -> str:
    if region.language in {"javascript", "typescript", "tsx"}:
        return _javascript_identity(node, region)
    if region.language in {"cpp", "rust", "php", "swift", "dart"}:
        return _second_wave_identity(node, region)
    if node.type in _MAINSTREAM_LAMBDA_TYPES[region.language]:
        return _mainstream_lambda_identity(node, region)
    source, language = region.source, region.language
    parts = [_name(node, language, source)]
    owner_types = {
        "python": {"class_definition", "function_definition"}, "go": set(),
        "kotlin": {"class_declaration", "object_declaration", "function_declaration"},
        "csharp": {"namespace_declaration", "file_scoped_namespace_declaration", "class_declaration", "struct_declaration", "record_declaration", "method_declaration", "constructor_declaration", "local_function_statement"},
        "java": {"class_declaration", "record_declaration", "enum_declaration", "method_declaration", "constructor_declaration"},
    }[language]
    for current in _ancestors(node):
        if current.type in owner_types:
            name = _name_node(current, language)
            if name:
                parts.append(node_text(name, source))
    if language == "go":
        receiver_type = _go_receiver_type(node, source)
        if receiver_type:
            parts.append(receiver_type)
    parts.append(region.original_path.stem if language == "python" else _package_or_namespace(node, language, source))
    return ".".join(reversed([part for part in parts if part]))


def is_anonymous_callable(node, region: ExecutableRegion) -> bool:
    if region.language in {"javascript", "typescript", "tsx"}:
        return _javascript_lexical_name(node, region.source) is None
    if node.type in _MAINSTREAM_LAMBDA_TYPES.get(region.language, set()):
        return True
    return _is_closure(node, region.language) and _second_wave_name(node, region.language, region.source) is None


def callable_source_start(node, language: str):
    if language == "python" and node.parent and node.parent.type == "decorated_definition":
        return node.parent
    if language in {"javascript", "typescript", "tsx"} and node.type in {"arrow_function", "function_expression"}:
        declarator = _ancestor(node, "variable_declarator")
        if declarator and declarator.child_by_field_name("value") == node:
            return declarator.parent if declarator.parent and declarator.parent.type in {"lexical_declaration", "variable_declaration"} else declarator
    if language in {"typescript", "tsx"} and node.type == "method_definition":
        first = node
        previous = node.prev_named_sibling
        while previous and previous.type == "decorator":
            first, previous = previous, previous.prev_named_sibling
        return first
    if language == "cpp" and node.parent and node.parent.type == "template_declaration":
        return node.parent
    if language in {"cpp", "php", "swift", "dart", "rust"} and _is_closure(node, language):
        owner = _assigned_closure_owner(node, language)
        if owner is not None:
            return owner
    if language == "swift" and node.type == "protocol_function_declaration" and node.prev_named_sibling:
        previous = node.prev_named_sibling
        if previous.type == "protocol_function_declaration" and previous.child_by_field_name("name") is not None:
            return previous
    return node


def _javascript_identity(node, region: ExecutableRegion) -> str:
    source = region.source
    name = node.child_by_field_name("name")
    if node.type in {"arrow_function", "function_expression"}:
        declarator = _ancestor(node, "variable_declarator")
        if declarator and declarator.child_by_field_name("value") == node:
            name = declarator.child_by_field_name("name")
    parts = [node_text(name, source) if name else _callback_name(node, region)]
    for current in _ancestors(node):
        owner = None
        if current.type == "class_declaration":
            owner = current.child_by_field_name("name")
        elif current.type == "method_definition" and current is not node:
            owner = current.child_by_field_name("name")
        elif current.type in {"function_declaration", "arrow_function", "function_expression"} and current is not node:
            lexical = _javascript_lexical_name(current, source)
            if lexical:
                parts.append(lexical)
        if owner:
            parts.append(node_text(owner, source))
    if node.type == "method_definition" and not any(value.type == "class_declaration" for value in _ancestors(node)):
        object_name = _object_assignment_name(node, source)
        if object_name:
            parts.append(object_name)
    parts.append(region.original_path.stem)
    return ".".join(reversed(parts))


def _name(node, language: str, source: bytes) -> str:
    name = _name_node(node, language)
    if name:
        return node_text(name, source)
    if language in {"kotlin", "csharp", "java"} and "constructor" in node.type:
        for owner in _ancestors(node):
            if owner.type in {"class_declaration", "object_declaration", "struct_declaration", "record_declaration", "enum_declaration"}:
                owner_name = _name_node(owner, language)
                if owner_name:
                    return node_text(owner_name, source)
    return "<anonymous>"


def _name_node(node, language: str):
    name = node.child_by_field_name("name")
    if name is None and language == "kotlin":
        name = next((child for child in node.named_children if child.type in {"simple_identifier", "type_identifier"}), None)
    return name


def _go_receiver_type(method_node, source: bytes) -> str | None:
    receiver = method_node.child_by_field_name("receiver")
    if receiver is None:
        return None
    words = node_text(receiver, source).replace("(", "").replace(")", "").replace("*", "").split()
    return words[-1] if words else "receiver"


def _second_wave_identity(node, region: ExecutableRegion) -> str:
    language, source = region.language, region.source
    name = _second_wave_name(node, language, source)
    parts = [name or _callback_name(node, region)]
    owner_types = {
        "cpp": {"namespace_definition", "class_specifier", "struct_specifier", "union_specifier", "function_definition"},
        "rust": {"trait_item", "impl_item", "function_item"},
        "php": {"namespace_definition", "class_declaration", "trait_declaration", "interface_declaration", "function_definition", "method_declaration"},
        "swift": {"class_declaration", "struct_declaration", "protocol_declaration", "function_declaration", "init_declaration"},
        "dart": {"class_definition", "function_signature", "constructor_signature", "lambda_expression"},
    }[language]
    for current in _ancestors(node):
        if current.type not in owner_types:
            continue
        owner = _second_wave_name(current, language, source)
        if owner:
            parts.append(owner)
    parts.append(region.original_path.stem)
    return ".".join(reversed(parts))


def _second_wave_name(node, language: str, source: bytes) -> str | None:
    name = node.child_by_field_name("name")
    if language == "cpp" and node.type == "function_definition":
        declarator = node.child_by_field_name("declarator")
        name = _deep_named_child(declarator, {"identifier", "field_identifier", "destructor_name", "operator_name"})
    elif language == "cpp" and node.type == "lambda_expression":
        name = _assigned_name(node, language)
    elif language == "rust" and node.type == "closure_expression":
        name = _assigned_name(node, language)
    elif language == "php" and node.type in {"arrow_function", "anonymous_function"}:
        name = _assigned_name(node, language)
    elif language == "swift" and node.type == "init_declaration":
        return "init"
    elif language == "swift" and node.type == "protocol_function_declaration" and name is None:
        previous = node.prev_named_sibling
        name = previous.child_by_field_name("name") if previous is not None else None
    elif language == "swift" and node.type == "lambda_literal":
        name = _assigned_name(node, language)
    elif language == "dart" and node.type in {"function_expression", "lambda_expression"}:
        signature = next((child for child in node.named_children if child.type == "function_signature"), None)
        name = signature.child_by_field_name("name") if signature is not None else _assigned_name(node, language)
    elif language == "dart" and node.type == "method_signature":
        return _dart_method_name(node, source)
    elif language == "dart" and node.type == "class_definition":
        name = node.child_by_field_name("name")
    elif language == "rust" and node.type == "impl_item":
        name = node.child_by_field_name("type")
    if name is None and language == "swift" and node.type == "class_declaration":
        name = next((child for child in node.named_children if child.type in {"type_identifier", "user_type"}), None)
    return node_text(name, source).lstrip("$") if name is not None else None


def _dart_method_name(method_signature, source: bytes) -> str | None:
    signature = next((child for child in method_signature.named_children if child.type in {
        "function_signature", "constructor_signature", "factory_constructor_signature",
    }), None)
    if signature is None:
        return None
    if signature.type in {"constructor_signature", "factory_constructor_signature"}:
        return _dart_constructor_name(signature, source)
    name = signature.child_by_field_name("name")
    return node_text(name, source).lstrip("$") if name is not None else None


def _dart_constructor_name(signature, source: bytes) -> str | None:
    identifiers = [child for child in signature.named_children if child.type == "identifier"]
    return ".".join(node_text(child, source).lstrip("$") for child in identifiers) or None


def _deep_named_child(node, types: set[str]):
    if node is None:
        return None
    if node.type in types:
        return node
    for child in node.named_children:
        found = _deep_named_child(child, types)
        if found is not None:
            return found
    return None


def _is_closure(node, language: str) -> bool:
    return node.type in {
        "cpp": {"lambda_expression"}, "rust": {"closure_expression"},
        "php": {"arrow_function", "anonymous_function"},
        "swift": {"lambda_literal"}, "dart": {"function_expression", "lambda_expression"},
    }.get(language, set())


def _assigned_name(node, language: str):
    owner = _assigned_closure_owner(node, language)
    if owner is None:
        return None
    candidates = {
        "cpp": {"identifier"}, "rust": {"identifier"}, "php": {"variable_name"},
        "swift": {"pattern"}, "dart": {"identifier"},
    }[language]
    return _deep_named_child(owner, candidates)


def _assigned_closure_owner(node, language: str):
    if language == "php":
        assignment = _ancestor(node, "assignment_expression")
        if assignment is None or assignment.child_by_field_name("right") != node:
            return None
        return assignment.parent if assignment.parent and assignment.parent.type == "expression_statement" else assignment
    owner_types = {
        "cpp": {"declaration"}, "rust": {"let_declaration"},
        "swift": {"property_declaration"}, "dart": {"local_variable_declaration"},
    }[language]
    current = node.parent
    while current and current.type not in CALLABLE_TYPES[language]:
        if current.type in owner_types:
            return current
        current = current.parent
    return None


def _package_or_namespace(node, language: str, source: bytes) -> str:
    root = node
    while root.parent:
        root = root.parent
    types = {"go": {"package_clause"}, "kotlin": {"package_header"}, "csharp": {"file_scoped_namespace_declaration"}, "java": {"package_declaration"}}.get(language, set())
    for child in root.named_children:
        if child.type in types:
            return node_text(child, source).replace("package", "", 1).replace("namespace", "", 1).strip().rstrip(";")
    return ""


def _javascript_lexical_name(node, source: bytes) -> str | None:
    name = node.child_by_field_name("name")
    if name:
        return node_text(name, source)
    declarator = _ancestor(node, "variable_declarator")
    if declarator and declarator.child_by_field_name("value") == node:
        target = declarator.child_by_field_name("name")
        if target and target.type in {"identifier", "property_identifier"}:
            return node_text(target, source)
    return None


def _callback_name(node, region: ExecutableRegion) -> str:
    point = region.original_point_at_byte(node.start_byte)
    return f"<callback@{point.line}:{point.byte_column}>"


_MAINSTREAM_LAMBDA_TYPES = {
    "python": {"lambda"}, "go": {"func_literal"},
    "kotlin": {"lambda_literal", "anonymous_function"},
    "csharp": {"lambda_expression", "anonymous_method_expression"},
    "java": {"lambda_expression"},
}


def _mainstream_lambda_identity(node, region: ExecutableRegion) -> str:
    parts = [_callback_name(node, region)]
    for current in _ancestors(node):
        if current.type in _MAINSTREAM_LAMBDA_TYPES[region.language]:
            parts.append(_callback_name(current, region))
        elif current.type in CALLABLE_TYPES[region.language]:
            name = _name_node(current, region.language)
            if name is not None:
                parts.append(node_text(name, region.source))
                if region.language == "go" and current.type == "method_declaration":
                    receiver_type = _go_receiver_type(current, region.source)
                    if receiver_type:
                        parts.append(receiver_type)
        elif current.type in {"class_definition", "class_declaration", "object_declaration", "struct_declaration", "record_declaration", "enum_declaration"}:
            name = _name_node(current, region.language)
            if name is not None:
                parts.append(node_text(name, region.source))
    parts.append(region.original_path.stem if region.language == "python" else _package_or_namespace(node, region.language, region.source))
    return ".".join(reversed([part for part in parts if part]))


def _object_assignment_name(node, source: bytes) -> str | None:
    object_node = _ancestor(node, "object")
    declarator = _ancestor(object_node, "variable_declarator") if object_node else None
    target = declarator.child_by_field_name("name") if declarator else None
    return node_text(target, source) if target and target.type == "identifier" else None


def _ancestor(node, node_type: str):
    current = node.parent if node else None
    while current:
        if current.type == node_type:
            return current
        current = current.parent
    return None


def _ancestors(node) -> Iterator:
    current = node.parent
    while current:
        yield current
        current = current.parent
