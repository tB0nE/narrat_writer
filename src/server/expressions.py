def evaluate_expression(expr: str, variables: dict) -> bool:
    """Simple expression evaluator for if statements."""
    try:
        if expr.startswith("(") and expr.endswith(")"):
            expr = expr[1:-1].strip()
        parts = expr.split()
        
        def get_val(v):
            if v.startswith("$"):
                raw_path = v[1:]
                clean_path = raw_path[5:] if raw_path.startswith("data.") else raw_path
                path = clean_path.split(".")
                curr = variables
                for p in path:
                    if isinstance(curr, dict) and p in curr:
                        curr = curr[p]
                    else:
                        return 0
                return curr
            return int(v) if v.isdigit() else v.strip('"').strip("'")

        if len(parts) == 1:
            val_str = parts[0]
            if val_str.startswith("$"): return bool(get_val(val_str))
            return val_str.lower() == "true"
        
        op = parts[0]
        if op == "==": return get_val(parts[1]) == get_val(parts[2])
        if op == "!=": return get_val(parts[1]) != get_val(parts[2])
        if op == ">": return get_val(parts[1]) > get_val(parts[2])
        if op == "<": return get_val(parts[1]) < get_val(parts[2])
        if op == ">=": return get_val(parts[1]) >= get_val(parts[2])
        if op == "<=": return get_val(parts[1]) <= get_val(parts[2])
        return False
    except: return False
