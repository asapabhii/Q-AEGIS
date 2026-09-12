# Policy Evaluator Rego Module
# 
# This module evaluates policy rules against document context.
# Rules are data (jsonb condition trees), NOT generated Rego code.
# 
# IMPORTANT:
# - This module takes rules and context as INPUT, it does NOT generate policy source
# - Evaluation is priority-ordered first match (lower priority = evaluated first)
# - First matching rule wins, evaluation stops
# - "no rule fired" is the common case (returns null rule_id)

package policy

import future.keywords

# Input schema:
# {
#   \"rules\": [
#     {
#       \"id\": \"uuid\",
#       \"rule_name\": \"string\",
#       \"condition_expr\": {...},  # condition tree
#       \"action\": \"allow\" | \"deny\" | \"require_mfa\" | \"force_pqc\",
#       \"priority\": number  # lower = evaluated first
#     }
#   ],
#   \"context\": {
#     \"document_id\": \"uuid\",
#     \"sensitivity\": \"string\",
#     \"trust_score\": number,
#     ...
#   }
# }

# Default decision when no rule matches
default decision = {
    \"matched\": false,
    \"rule_id\": null,
    \"rule_name\": null,
    \"action\": null,
    \"rationale\": \"No rule matched the current context\"
}

# Main decision rule - evaluates rules in priority order
decision = result {
    # Sort rules by priority (ascending - lower priority first)
    sorted_rules := sort_by(input.rules, func(a, b) a.priority < b.priority)
    
    # Find first matching rule
    some i
    rule := sorted_rules[i]
    evaluate_condition(rule.condition_expr, input.context)
    
    result := {
        \"matched\": true,
        \"rule_id\": rule.id,
        \"rule_name\": rule.rule_name,
        \"action\": rule.action,
        \"rationale\": sprintf(\"Rule '%s' matched with action '%s'\", [rule.rule_name, rule.action])
    }
}

# Condition evaluation - handles the condition tree structure
# 
# Condition tree format (from FR-13 rule builder):
# {
#   \"op\": \"eq\" | \"neq\" | \"gt\" | \"gte\" | \"lt\" | \"lte\" | \"in\" | \"and\" | \"or\" | \"not\",
#   \"field\": \"path.to.field\",  # for binary operators
#   \"value\": ...               # for binary operators
#   \"children\": [...]          # for logical operators
#   \"right\": ...               # alternative for binary operators
# }

evaluate_condition(condition, context) {
    condition.op == \"eq\"
    get_value(context, condition.field) == condition.value
}

evaluate_condition(condition, context) {
    condition.op == \"neq\"
    get_value(context, condition.field) != condition.value
}

evaluate_condition(condition, context) {
    condition.op == \"gt\"
    get_value(context, condition.field) > condition.value
}

evaluate_condition(condition, context) {
    condition.op == \"gte\"
    get_value(context, condition.field) >= condition.value
}

evaluate_condition(condition, context) {
    condition.op == \"lt\"
    get_value(context, condition.field) < condition.value
}

evaluate_condition(condition, context) {
    condition.op == \"lte\"
    get_value(context, condition.field) <= condition.value
}

evaluate_condition(condition, context) {
    condition.op == \"in\"
    get_value(context, condition.field) == condition.value
}

evaluate_condition(condition, context) {
    condition.op == \"and\"
    evaluate_condition(condition.children[0], context)
    evaluate_condition(condition.children[1], context)
}

evaluate_condition(condition, context) {
    condition.op == \"or\"
    evaluate_condition(condition.children[0], context)
}

evaluate_condition(condition, context) {
    condition.op == \"or\"
    evaluate_condition(condition.children[1], context)
}

evaluate_condition(condition, context) {
    condition.op == \"not\"
    not evaluate_condition(condition.children[0], context)
}

# Helper to get nested value from context using dot-notation path
get_value(obj, path) = result {
    parts := split(path, \".\")
    result := _get_nested(obj, parts, 0)
}

_get_nested(obj, parts, idx) = result {
    idx >= count(parts)
    result := obj
}

_get_nested(obj, parts, idx) = result {
    idx < count(parts)
    part := parts[idx]
    result := _get_nested(obj[part], parts, idx + 1)
}