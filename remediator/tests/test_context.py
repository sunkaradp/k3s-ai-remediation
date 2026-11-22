from app import context


def test_escape_logql_label_quotes_and_backslashes():
    assert context._escape_logql_label('api"name\\part') == 'api\\"name\\\\part'


def test_escape_logql_label_newlines():
    assert context._escape_logql_label("api\nname\r") == "api\\nname\\r"


def test_log_line_limit_is_bounded():
    assert 1 <= context.LOG_LINES <= 500
