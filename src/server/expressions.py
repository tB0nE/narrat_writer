
import re
import random
import logging

logger = logging.getLogger("narrat_api")

def evaluate_expression(expr: str, variables: dict) -> bool:
    """
    Evaluator for Narrat-style prefix notation expressions.
    Handles variables with or without $, numbers, booleans, and functions like roll.
    """
    try:
        expr = expr.strip()
        if expr.startswith("(") and expr.endswith(")"):
            expr = expr[1:-1].strip()
        
        # Tokenize carefully to handle multi-character operators and quotes
        tokens = re.findall(r'"[^"]*"|\'[^\']*\'|\$?\w+(?:\.[\w.]+)*|==|!=|>=|<=|&&|\|\||[^\s\w$.]', expr)
        if not tokens: return False

        def get_val(v):
            if not v: return None
            v_lower = v.lower()
            if v_lower == "true": return True
            if v_lower == "false": return False
            if v.isdigit(): return int(v)
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                return v[1:-1]
            
            # Resolve as variable (loose handling of $)
            raw_path = v[1:] if v.startswith("$") else v
            clean_path = raw_path[5:] if raw_path.startswith("data.") else raw_path
            path = clean_path.split(".")
            curr = variables
            for p in path:
                if isinstance(curr, dict) and p in curr:
                    curr = curr[p]
                else:
                    return None
            return curr

        op = tokens[0]
        
        if op == "roll":
            # (roll id stat threshold) -> threshold is usually the 4th token
            try:
                threshold = int(get_val(tokens[3]))
                return random.randint(1, 100) >= threshold
            except: return False

        if op == "!":
            return not bool(get_val(tokens[1]))
        
        if op == "&&":
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
            
        # Fallback for single value or variable
        return bool(get_val(op))

    except Exception as e:
        logger.error(f"Expression error: {expr} -> {e}")
        return False
