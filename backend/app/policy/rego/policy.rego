# Interprets a closed condition tree of bounded depth.
# Recursion is forbidden in Rego (evaluation must terminate), so combinators
# are unrolled. matches_k handles combinator-depth 0..k-1 (a leaf is depth 0).
# Entry is matches_9 so MAX_TREE_DEPTH=8 in Python is the deepest tree this
# module can evaluate. Python rejects a deeper tree (422) before it gets here.
# Rules are data on input, never generated as Rego.
#
# Package: q_aegis.policy
# Entrypoint: first_match  (undefined when no rule matches)

package q_aegis.policy

import rego.v1

first_match := rules_that_match[0] if {
	count(rules_that_match) > 0
}

rules_that_match := [rule |
	some rule in input.rules
	matches_9(rule.condition, input.document)
]

leaf_match(cond, doc) if {
	cond.op == "eq"
	object.get(doc, cond.field, null) == cond.value
}

leaf_match(cond, doc) if {
	cond.op == "neq"
	object.get(doc, cond.field, null) != cond.value
}

leaf_match(cond, doc) if {
	cond.op == "gt"
	object.get(doc, cond.field, null) > cond.value
}

leaf_match(cond, doc) if {
	cond.op == "gte"
	object.get(doc, cond.field, null) >= cond.value
}

leaf_match(cond, doc) if {
	cond.op == "lt"
	object.get(doc, cond.field, null) < cond.value
}

leaf_match(cond, doc) if {
	cond.op == "lte"
	object.get(doc, cond.field, null) <= cond.value
}

leaf_match(cond, doc) if {
	cond.op == "in"
	object.get(doc, cond.field, null) in object.get(cond, "value", [])
}

matches_1(cond, doc) if {
	leaf_match(cond, doc)
}

matches_2(cond, doc) if {
	leaf_match(cond, doc)
}

matches_2(cond, doc) if {
	object.get(cond, "all", null) != null
	count([c |
		some c in object.get(cond, "all", [])
		matches_1(c, doc)
	]) == count(object.get(cond, "all", []))
}

matches_2(cond, doc) if {
	object.get(cond, "any", null) != null
	some c in object.get(cond, "any", [])
	matches_1(c, doc)
}

matches_2(cond, doc) if {
	object.get(cond, "not", null) != null
	not matches_1(object.get(cond, "not", {}), doc)
}


matches_3(cond, doc) if {
	leaf_match(cond, doc)
}

matches_3(cond, doc) if {
	object.get(cond, "all", null) != null
	count([c |
		some c in object.get(cond, "all", [])
		matches_2(c, doc)
	]) == count(object.get(cond, "all", []))
}

matches_3(cond, doc) if {
	object.get(cond, "any", null) != null
	some c in object.get(cond, "any", [])
	matches_2(c, doc)
}

matches_3(cond, doc) if {
	object.get(cond, "not", null) != null
	not matches_2(object.get(cond, "not", {}), doc)
}


matches_4(cond, doc) if {
	leaf_match(cond, doc)
}

matches_4(cond, doc) if {
	object.get(cond, "all", null) != null
	count([c |
		some c in object.get(cond, "all", [])
		matches_3(c, doc)
	]) == count(object.get(cond, "all", []))
}

matches_4(cond, doc) if {
	object.get(cond, "any", null) != null
	some c in object.get(cond, "any", [])
	matches_3(c, doc)
}

matches_4(cond, doc) if {
	object.get(cond, "not", null) != null
	not matches_3(object.get(cond, "not", {}), doc)
}


matches_5(cond, doc) if {
	leaf_match(cond, doc)
}

matches_5(cond, doc) if {
	object.get(cond, "all", null) != null
	count([c |
		some c in object.get(cond, "all", [])
		matches_4(c, doc)
	]) == count(object.get(cond, "all", []))
}

matches_5(cond, doc) if {
	object.get(cond, "any", null) != null
	some c in object.get(cond, "any", [])
	matches_4(c, doc)
}

matches_5(cond, doc) if {
	object.get(cond, "not", null) != null
	not matches_4(object.get(cond, "not", {}), doc)
}


matches_6(cond, doc) if {
	leaf_match(cond, doc)
}

matches_6(cond, doc) if {
	object.get(cond, "all", null) != null
	count([c |
		some c in object.get(cond, "all", [])
		matches_5(c, doc)
	]) == count(object.get(cond, "all", []))
}

matches_6(cond, doc) if {
	object.get(cond, "any", null) != null
	some c in object.get(cond, "any", [])
	matches_5(c, doc)
}

matches_6(cond, doc) if {
	object.get(cond, "not", null) != null
	not matches_5(object.get(cond, "not", {}), doc)
}


matches_7(cond, doc) if {
	leaf_match(cond, doc)
}

matches_7(cond, doc) if {
	object.get(cond, "all", null) != null
	count([c |
		some c in object.get(cond, "all", [])
		matches_6(c, doc)
	]) == count(object.get(cond, "all", []))
}

matches_7(cond, doc) if {
	object.get(cond, "any", null) != null
	some c in object.get(cond, "any", [])
	matches_6(c, doc)
}

matches_7(cond, doc) if {
	object.get(cond, "not", null) != null
	not matches_6(object.get(cond, "not", {}), doc)
}


matches_8(cond, doc) if {
	leaf_match(cond, doc)
}

matches_8(cond, doc) if {
	object.get(cond, "all", null) != null
	count([c |
		some c in object.get(cond, "all", [])
		matches_7(c, doc)
	]) == count(object.get(cond, "all", []))
}

matches_8(cond, doc) if {
	object.get(cond, "any", null) != null
	some c in object.get(cond, "any", [])
	matches_7(c, doc)
}

matches_8(cond, doc) if {
	object.get(cond, "not", null) != null
	not matches_7(object.get(cond, "not", {}), doc)
}


matches_9(cond, doc) if {
	leaf_match(cond, doc)
}

matches_9(cond, doc) if {
	object.get(cond, "all", null) != null
	count([c |
		some c in object.get(cond, "all", [])
		matches_8(c, doc)
	]) == count(object.get(cond, "all", []))
}

matches_9(cond, doc) if {
	object.get(cond, "any", null) != null
	some c in object.get(cond, "any", [])
	matches_8(c, doc)
}

matches_9(cond, doc) if {
	object.get(cond, "not", null) != null
	not matches_8(object.get(cond, "not", {}), doc)
}

