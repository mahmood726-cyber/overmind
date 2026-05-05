import sys, json
sys.path.insert(0, ".")
from aact_local_gateway import (
    validate_sql, convert_postgres_placeholders, ALLOWED_QUERY_IDS, FORBIDDEN_SQL_TOKENS,
)

# validate_sql contract: returns (ok, reason). Several deterministic cases.
v_select = validate_sql("SELECT * FROM studies WHERE nct_id = $1")
v_insert = validate_sql("INSERT INTO studies VALUES ($1)")
v_update = validate_sql("UPDATE studies SET x = $1")
v_drop   = validate_sql("DROP TABLE studies")
v_select_with_drop_string = validate_sql("SELECT 'drop' FROM studies")  # should pass — keyword in literal

# Placeholder conversion: $1 → %s
sql_in = "SELECT * FROM x WHERE a = $1 AND b = $2"
sql_out, params_out = convert_postgres_placeholders(sql_in, ["foo", "bar"])

print(json.dumps({
    "v_select_ok":      v_select[0],
    "v_insert_ok":      v_insert[0],
    "v_update_ok":      v_update[0],
    "v_drop_ok":        v_drop[0],
    "v_select_drop_lit_ok": v_select_with_drop_string[0],
    "n_allowed_queries": len(ALLOWED_QUERY_IDS),
    "n_forbidden_tokens": len(FORBIDDEN_SQL_TOKENS),
    "sql_out": sql_out,
    "n_params_out": len(params_out),
}))