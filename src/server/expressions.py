
import re

def evaluate_expression(expr: str, variables: dict) -> bool:
    """
    Evaluator for Narrat-style prefix notation expressions.
    Example: (&& $data.a $data.b) or (!= $data.intro.feelFace true)
    """
    try:
        expr = expr.strip()
        if expr.startswith("(") and expr.endswith(")"):
            expr = expr[1:-1].strip()
        
        # Tokenize carefully to handle quotes
        tokens = re.findall(r'"[^"]*"|\'[^\']*\'|\$?\w+(?:\.[\w.]+)*|[^\s\w$.]', expr)
        if not tokens: return False

        def get_val(v):
            if v.startswith("$"):
                raw_path = v[1:]
                # Narrat often uses $data.something, we strip $data. if it's there
                # as our variables dict usually starts from 'data' being root or implicit
                clean_path = raw_path[5:] if raw_path.startswith("data.") else raw_path
                path = clean_path.split(".")
                curr = variables
                for p in path:
                    if isinstance(curr, dict) and p in curr:
                        curr = curr[p]
                    else:
                        return None
                return curr
            if v.lower() == "true": return True
            if v.lower() == "false": return False
            if v.isdigit(): return int(v)
            return v.strip('"').strip("'")

        # Handle prefix operators
        op = tokens[0]
        
        if op == "!":
            return not bool(get_val(tokens[1]))
        
        if op == "&&":
            # (&& val1 val2 val3 ...)
            return all(bool(get_val(t)) for t in tokens[1:])
        
        if op == "||":
            return any(bool(get_val(t)) for t in tokens[1:])

        if op == "==":
            return get_val(tokens[1]) == get_val(tokens[2])
        
        if op == "!=":
            return get_val(tokens[1]) != get_val(tokens[2])
        
        if op == ">":
            return get_val(tokens[1]) > get_val(tokens[2])
        
        if op == "<":
            return get_val(tokens[1]) < get_val(tokens[2])
        
        if op == ">=":
            return get_val(tokens[1]) >= get_val(tokens[2])
        
        if op == "<=":
            return get_val(tokens[1]) <= get_val(tokens[2])
            
        # Fallback for single value
        return bool(get_val(op))

    except Exception as e:
        import logging
        logging.getLogger("narrat_api").error(f"Expression error: {expr} -> {e}")
        return False
