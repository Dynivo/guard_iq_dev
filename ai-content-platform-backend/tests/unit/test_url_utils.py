"""Unit tests for URL normalization and hashing."""

from __future__ import annotations

from app.shared.url_utils import hash_content, hash_url, normalize_url


class TestNormalizeUrl:
    def test_strips_utm_params(self) -> None:
        raw = "https://example.com/article?utm_source=twitter&utm_medium=social&id=42"
        result = normalize_url(raw)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=42" in result

    def test_lowercases_host(self) -> None:
        raw = "https://Example.COM/Path/To/Article"
        result = normalize_url(raw)
        assert result.startswith("https://example.com/")

    def test_removes_trailing_slash(self) -> None:
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_preserves_path(self) -> None:
        raw = "https://example.com/blog/2024/my-post"
        result = normalize_url(raw)
        assert "/blog/2024/my-post" in result

    def test_sorts_query_params(self) -> None:
        raw = "https://example.com/search?z=1&a=2"
        result = normalize_url(raw)
        assert "a=2" in result
        assert "z=1" in result
        assert result.index("a=2") < result.index("z=1")

    def test_strips_fbclid(self) -> None:
        raw = "https://example.com/article?fbclid=abc123"
        result = normalize_url(raw)
        assert "fbclid" not in result

    def test_strips_gclid(self) -> None:
        raw = "https://example.com/page?gclid=xyz789&real=yes"
        result = normalize_url(raw)
        assert "gclid" not in result
        assert "real=yes" in result

    def test_default_scheme_is_https(self) -> None:
        raw = "//example.com/page"
        result = normalize_url(raw)
        assert result.startswith("https://")

    def test_removes_default_https_port(self) -> None:
        raw = "https://example.com:443/page"
        result = normalize_url(raw)
        assert ":443" not in result

    def test_preserves_non_default_port(self) -> None:
        raw = "https://example.com:8080/page"
        result = normalize_url(raw)
        assert ":8080" in result

    def test_root_path_preserved(self) -> None:
        raw = "https://example.com"
        result = normalize_url(raw)
        assert result == "https://example.com/"

    def test_empty_query_no_question_mark(self) -> None:
        raw = "https://example.com/page?utm_source=x"
        result = normalize_url(raw)
        assert "?" not in result

    def test_identical_urls_same_hash(self) -> None:
        url_a = "https://Example.COM/article?utm_source=tw"
        url_b = "https://example.com/article"
        assert hash_url(url_a) == hash_url(url_b)

    def test_different_urls_different_hash(self) -> None:
        assert hash_url("https://a.com/1") != hash_url("https://a.com/2")


class TestHashContent:
    def test_whitespace_invariant(self) -> None:
        a = hash_content("Hello   World\n\t!")
        b = hash_content("hello world !")
        assert a == b

    def test_different_content_different_hash(self) -> None:
        assert hash_content("article one") != hash_content("article two")
