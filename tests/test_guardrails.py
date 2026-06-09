from src.agent.guardrails import validate_sql_safety


class TestSQLSafetyValidation:
    def test_destructive_sql_blocked(self):
        destructive_statements = [
            "DROP TABLE srag.srag_cases;",
            "DELETE FROM srag.srag_cases;",
            "UPDATE srag.srag_cases SET evolucao = 1;",
            "INSERT INTO srag.srag_cases VALUES (1, 2, 3);",
        ]
        for stmt in destructive_statements:
            is_safe, reason = validate_sql_safety(stmt)
            assert not is_safe, f"Should block: {stmt}"
            assert reason, f"Should provide reason for: {stmt}"

    def test_ddl_blocked(self):
        ddl_statements = [
            "ALTER TABLE srag.srag_cases ADD COLUMN test INT;",
            "TRUNCATE TABLE srag.srag_cases;",
            "CREATE TABLE test (id INT);",
            "GRANT ALL ON srag.srag_cases TO public;",
        ]
        for stmt in ddl_statements:
            is_safe, reason = validate_sql_safety(stmt)
            assert not is_safe, f"Should block DDL: {stmt}"

    def test_multi_statement_blocked(self):
        stmt = "SELECT COUNT(*) FROM srag.srag_cases; SELECT 1;"
        is_safe, reason = validate_sql_safety(stmt)
        assert not is_safe

    def test_select_star_without_where_blocked(self):
        stmt = "SELECT * FROM srag.srag_cases"
        is_safe, reason = validate_sql_safety(stmt)
        assert not is_safe

    def test_valid_select_passes(self):
        stmt = "SELECT COUNT(*) FROM srag.srag_cases WHERE caso_confirmado = true"
        is_safe, reason = validate_sql_safety(stmt)
        assert is_safe

    def test_select_with_limit_passes(self):
        stmt = "SELECT * FROM srag.srag_cases WHERE caso_confirmado = true LIMIT 10"
        is_safe, reason = validate_sql_safety(stmt)
        assert is_safe
