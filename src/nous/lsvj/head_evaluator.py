"""M1: head-expression evaluator for LSVJ-S Datalog rules.

The LSVJ-S rule shape is:
    ?[discharged] := prim1(args), prim2(args), ..., discharged = <bool_expr>

M0 (`_execute_rule` in gate.py) ignored `<bool_expr>` and returned
`AND(all primitive evaluations)`. That collapses OR/NOT-shaped rules
(most of our seed library) to wrong verdicts.

This module provides the proper evaluator:
    evaluate_head_expr(rule_text, evaluator) -> bool | None
        Returns None when Lark cannot parse the rule (caller falls back
        to M0 AND semantics for backward compatibility). Returns the
        boolean value of the head expression otherwise.

The Lark grammar (obligation.lark) restricts atoms to IDENTIFIER /
BOOLEAN / parenthesized expr. Some seed rules inline primitive_call
atoms in the head (e.g. `not (regex(...) and external(...))`); the
extractor in compiler.py walks the whole tree so this works in
practice. We mirror that walk here, evaluating atoms encountered.
"""

from __future__ import annotations

from typing import Any, Optional

from nous.lsvj.compiler import _LARK_AVAILABLE, _get_lark_parser


def evaluate_head_expr(
    rule_text: str,
    evaluator: Any,
) -> Optional[bool]:
    """Return the boolean value of `discharged = <expr>`.

    Returns None if the rule cannot be parsed by Lark (caller should
    fall back to AND semantics). Returns True/False otherwise.

    `evaluator` must implement
        evaluate(prim_id: str, args: list[str], bindings: dict) -> bool
    (matches lsvj.gate.Evaluator Protocol).
    """
    if not _LARK_AVAILABLE:
        return None

    # Lark grammar requires the full `?[discharged] := <body>` shape.
    # ParsedRule.raw in practice often contains only the body (rule_text
    # passed to parse_rule without the prefix). Try both forms.
    text = rule_text.strip()
    parser = _get_lark_parser()
    tree = None
    for candidate in (text, f"?[discharged] := {text}"):
        try:
            tree = parser.parse(candidate)
            break
        except Exception:
            continue
    if tree is None:
        return None

    head_tree = _find_head_expr(tree)
    if head_tree is None:
        return None

    # Pre-populate cache with body primitive evaluations.
    # Cache key is (prim_id, args_tuple) to avoid collisions when the
    # same primitive is called with different argument lists. IDENTIFIER
    # atoms in the head (which reference the body-side name) are
    # resolved against the last-seen value for that name; recorded
    # separately under the bare name key.
    cache: dict = {}
    body_calls = _collect_body_primitive_calls(tree)
    for prim_id, args in body_calls:
        val = bool(evaluator.evaluate(prim_id, list(args), {}))
        cache[(prim_id, tuple(args))] = val
        # Also surface under bare name so head IDENTIFIER atoms resolve.
        cache[prim_id] = val

    return _eval_node(head_tree, evaluator, cache)


# ---------------------------------------------------------------- helpers

def _find_head_expr(tree: Any) -> Any:
    """Return the first `head_expr` Tree node found by DFS, or None."""
    if hasattr(tree, "data") and tree.data == "head_expr":
        return tree
    if hasattr(tree, "children"):
        for child in tree.children:
            if hasattr(child, "data"):
                found = _find_head_expr(child)
                if found is not None:
                    return found
    return None


def _collect_body_primitive_calls(tree: Any) -> list[tuple[str, list[str]]]:
    """Collect (prim_id, args) for primitive_calls in the body
    (excluding any inside head_expr).
    """
    results: list[tuple[str, list[str]]] = []
    _walk_collect(tree, results)
    return results


def _walk_collect(node: Any, out: list) -> None:
    if not hasattr(node, "data"):
        return
    if node.data == "head_expr":
        return  # skip the head sub-tree
    if node.data == "primitive_call":
        prim_id = str(node.children[0])
        args: list[str] = []
        for child in node.children:
            if hasattr(child, "data") and child.data == "arg_list":
                for arg_node in child.children:
                    if hasattr(arg_node, "data") and arg_node.data == "arg":
                        args.append(str(arg_node.children[0]))
        out.append((prim_id, args))
        return
    if hasattr(node, "children"):
        for child in node.children:
            _walk_collect(child, out)


# ---------------------------------------------------------------- evaluator

def _eval_node(node: Any, evaluator: Any, cache: dict[str, bool]) -> bool:
    """Evaluate a head_expr / or_expr / and_expr / not_expr / atom node."""
    if not hasattr(node, "data"):
        return _eval_identifier(str(node), cache)

    data = node.data
    children = list(node.children)

    if data == "head_expr":
        return _eval_node(children[0], evaluator, cache)

    if data == "or_expr":
        # children: [and_expr, KW_OR, and_expr, KW_OR, ...]
        # Guard i+1 < len(children) defensively so malformed trees
        # raise cleanly rather than IndexError (which _execute_rule's
        # except-block would silently swallow into M0 fallback).
        result = _eval_node(children[0], evaluator, cache)
        i = 1
        while i + 1 < len(children):
            if result:
                return True
            result = _eval_node(children[i + 1], evaluator, cache)
            i += 2
        return result

    if data == "and_expr":
        result = _eval_node(children[0], evaluator, cache)
        i = 1
        while i + 1 < len(children):
            if not result:
                return False
            result = _eval_node(children[i + 1], evaluator, cache)
            i += 2
        return result

    if data == "not_expr":
        # The non-negated branch produces an atom directly; pass through.
        return _eval_node(children[0], evaluator, cache)

    if data == "negation":
        # Tree shape per Lark: children = [KW_NOT token, atom]. The first
        # child is the literal "not" token, the second is the atom to negate.
        # Find the first child that is itself a Tree (skip the keyword token).
        for c in children:
            if hasattr(c, "data"):
                return not _eval_node(c, evaluator, cache)
        # Fallback: treat all children as the atom (no Tree found)
        return not _eval_node(children[-1], evaluator, cache)

    if data == "atom":
        c = children[0]
        if hasattr(c, "data"):
            return _eval_node(c, evaluator, cache)
        token_type = getattr(c, "type", "")
        text = str(c)
        if token_type == "IDENTIFIER":
            return _eval_identifier(text, cache)
        if token_type == "BOOLEAN":
            return text.lower() == "true"
        return _eval_identifier(text, cache)

    if data == "primitive_call":
        prim_id = str(children[0])
        args: list[str] = []
        for child in children:
            if hasattr(child, "data") and child.data == "arg_list":
                for arg_node in child.children:
                    if hasattr(arg_node, "data") and arg_node.data == "arg":
                        args.append(str(arg_node.children[0]))
        key = (prim_id, tuple(args))
        if key not in cache:
            val = bool(evaluator.evaluate(prim_id, args, {}))
            cache[key] = val
            # Last-seen value under bare name for head IDENTIFIER atoms.
            cache[prim_id] = val
        return cache[key]

    return False


def _eval_identifier(name: str, cache: dict[str, bool]) -> bool:
    """Look up an IDENTIFIER atom in the cache. Absent -> False."""
    return bool(cache.get(name, False))
