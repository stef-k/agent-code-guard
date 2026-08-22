"""Declarative Tree-sitter node mappings for supported executable languages."""

CALLABLE_TYPES = {
    "python": {"function_definition"}, "go": {"function_declaration", "method_declaration"},
    "kotlin": {"function_declaration", "secondary_constructor"},
    "csharp": {"method_declaration", "constructor_declaration", "local_function_statement"},
    "java": {"method_declaration", "constructor_declaration"},
    "javascript": {"function_declaration", "method_definition", "arrow_function", "function_expression"},
    "typescript": {"function_declaration", "method_definition", "arrow_function", "function_expression"},
    "tsx": {"function_declaration", "method_definition", "arrow_function", "function_expression"},
    "cpp": {"function_definition", "lambda_expression"}, "rust": {"function_item", "closure_expression"},
    "php": {"function_definition", "method_declaration", "anonymous_function", "arrow_function"},
    "swift": {"function_declaration", "init_declaration", "lambda_literal", "protocol_function_declaration"},
    "dart": {"function_signature", "method_signature", "function_expression", "lambda_expression"},
}

OPAQUE_LAMBDA_TYPES = {
    "python": {"lambda"}, "go": {"func_literal"}, "kotlin": {"lambda_literal", "anonymous_function"},
    "csharp": {"lambda_expression", "anonymous_method_expression"}, "java": {"lambda_expression"},
    "javascript": set(), "typescript": set(), "tsx": set(), "cpp": set(), "rust": set(),
    "php": set(), "swift": set(), "dart": set(),
}

CONTROL_CATEGORIES = {
    "if_statement": "condition", "if_expression": "condition", "elif_clause": "condition",
    "else_if_clause": "condition", "guard_statement": "condition", "for_statement": "loop",
    "foreach_statement": "loop", "enhanced_for_statement": "loop", "for_in_statement": "loop",
    "while_statement": "loop", "do_statement": "loop", "do_while_statement": "loop",
    "loop_expression": "loop", "while_expression": "loop", "for_expression": "loop",
    "repeat_while_statement": "loop", "match_statement": "selection", "match_expression": "selection",
    "when_expression": "selection", "switch_statement": "selection", "switch_expression": "selection",
    "expression_switch_statement": "selection", "type_switch_statement": "selection",
    "select_statement": "selection", "try_statement": "exception", "try_expression": "exception",
}

CONTROL_TYPES = {
    "python": {"if_statement", "elif_clause", "for_statement", "while_statement", "match_statement", "try_statement"},
    "go": {"if_statement", "for_statement", "expression_switch_statement", "type_switch_statement", "select_statement"},
    "kotlin": {"if_expression", "for_statement", "while_statement", "do_while_statement", "when_expression", "try_expression"},
    "csharp": {"if_statement", "for_statement", "foreach_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "java": {"if_statement", "for_statement", "enhanced_for_statement", "while_statement", "do_statement", "switch_expression", "try_statement"},
    "javascript": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "typescript": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "tsx": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "cpp": {"if_statement", "for_statement", "range_based_for_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
    "rust": {"if_expression", "loop_expression", "while_expression", "for_expression", "match_expression"},
    "php": {"if_statement", "else_if_clause", "for_statement", "foreach_statement", "while_statement", "do_statement", "switch_statement", "match_expression", "try_statement"},
    "swift": {"if_statement", "guard_statement", "for_statement", "while_statement", "repeat_while_statement", "switch_statement", "do_statement"},
    "dart": {"if_statement", "for_statement", "while_statement", "do_statement", "switch_statement", "try_statement"},
}

DECISION_CATEGORIES = {
    "if_statement": "condition", "if_expression": "condition", "elif_clause": "condition",
    "else_if_clause": "condition", "guard_statement": "condition", "for_statement": "loop",
    "foreach_statement": "loop", "enhanced_for_statement": "loop", "for_in_statement": "loop",
    "while_statement": "loop", "do_statement": "loop", "do_while_statement": "loop",
    "loop_expression": "loop", "while_expression": "loop", "for_expression": "loop",
    "repeat_while_statement": "loop", "except_clause": "catch", "catch_clause": "catch",
    "catch_block": "catch", "conditional_expression": "ternary", "ternary_expression": "ternary",
    "list_comprehension": "comprehension", "set_comprehension": "comprehension",
    "dictionary_comprehension": "comprehension", "generator_expression": "comprehension",
    "case_clause": "switch_arm", "expression_case": "switch_arm", "type_case": "switch_arm",
    "communication_case": "switch_arm", "when_entry": "switch_arm", "switch_expression_arm": "switch_arm",
    "match_arm": "switch_arm", "match_conditional_expression": "switch_arm", "switch_entry": "switch_arm",
    "switch_statement_case": "switch_arm", "case_statement": "switch_arm",
}

DECISION_TYPES = {
    "python": {"if_statement", "elif_clause", "for_statement", "while_statement", "except_clause", "conditional_expression", "list_comprehension", "set_comprehension", "dictionary_comprehension", "generator_expression", "case_clause"},
    "go": {"if_statement", "for_statement", "expression_case", "type_case", "communication_case"},
    "kotlin": {"if_expression", "for_statement", "while_statement", "do_while_statement", "catch_block", "when_entry"},
    "csharp": {"if_statement", "for_statement", "foreach_statement", "while_statement", "do_statement", "catch_clause", "conditional_expression", "switch_expression_arm"},
    "java": {"if_statement", "for_statement", "enhanced_for_statement", "while_statement", "do_statement", "catch_clause", "ternary_expression"},
    "javascript": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "catch_clause", "ternary_expression"},
    "typescript": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "catch_clause", "ternary_expression"},
    "tsx": {"if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement", "catch_clause", "ternary_expression"},
    "cpp": {"if_statement", "for_statement", "range_based_for_statement", "while_statement", "do_statement", "catch_clause", "conditional_expression", "case_statement"},
    "rust": {"if_expression", "loop_expression", "while_expression", "for_expression", "match_arm"},
    "php": {"if_statement", "else_if_clause", "for_statement", "foreach_statement", "while_statement", "do_statement", "catch_clause", "conditional_expression", "match_conditional_expression"},
    "swift": {"if_statement", "guard_statement", "for_statement", "while_statement", "repeat_while_statement", "catch_block", "ternary_expression", "switch_entry"},
    "dart": {"if_statement", "for_statement", "while_statement", "do_statement", "catch_clause", "conditional_expression", "switch_statement_case"},
}
