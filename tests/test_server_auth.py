from wpmchecker.server import is_authorized_path


def test_websocket_auth_is_optional_for_manual_development() -> None:
    assert is_authorized_path("/", None)


def test_websocket_auth_accepts_only_matching_query_token() -> None:
    assert is_authorized_path("/?token=correct", "correct")
    assert not is_authorized_path("/", "correct")
    assert not is_authorized_path("/?token=wrong", "correct")
    assert not is_authorized_path("/?token=correct&token=wrong", "correct")
