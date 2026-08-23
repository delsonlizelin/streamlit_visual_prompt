from __future__ import annotations

from io import BytesIO
import unittest

from url_documents import (
    MAX_URL_BYTES,
    UrlDocumentError,
    _read_bounded_response,
    extract_article_html,
    normalize_public_url,
)


def public_resolver(_hostname: str) -> list[str]:
    return ["93.184.216.34"]


class UrlDocumentTests(unittest.TestCase):
    def test_url_response_limit_is_large_but_still_bounded(self):
        self.assertEqual(MAX_URL_BYTES, 25 * 1024 * 1024)
        self.assertEqual(_read_bounded_response(BytesIO(b"x" * 10), max_bytes=10), b"x" * 10)
        with self.assertRaisesRegex(UrlDocumentError, "无法安全读取"):
            _read_bounded_response(BytesIO(b"x" * 11), max_bytes=10)

    def test_url_without_scheme_defaults_to_https_and_drops_fragment(self):
        value = normalize_public_url(
            "mp.weixin.qq.com/s/example?from=share#wechat_redirect",
            resolver=public_resolver,
        )
        self.assertEqual(value, "https://mp.weixin.qq.com/s/example?from=share")

    def test_local_and_credentialed_urls_are_rejected(self):
        with self.assertRaisesRegex(UrlDocumentError, "本机或内网"):
            normalize_public_url("http://localhost/admin", resolver=public_resolver)
        with self.assertRaisesRegex(UrlDocumentError, "格式不正确"):
            normalize_public_url(
                "https://user:password@example.com/article",
                resolver=public_resolver,
            )

    def test_wechat_article_prefers_js_content_and_keeps_metadata(self):
        body = "这是微信公众号正文，用于说明一个具体主题。" * 12
        html = f"""
        <html><head>
          <meta property="og:title" content="测试文章">
          <meta property="og:site_name" content="示例公众号">
        </head><body>
          <div id="js_name">作者甲</div>
          <em id="publish_time">2026-08-23</em>
          <nav>菜单和无关链接</nav>
          <div id="js_content"><h2>核心内容</h2><p>{body}</p></div>
          <footer>版权和推荐内容不应进入正文</footer>
        </body></html>
        """
        document = extract_article_html(
            html,
            url="https://mp.weixin.qq.com/s/example",
        )
        self.assertEqual(document.title, "测试文章")
        self.assertEqual(document.site, "示例公众号")
        self.assertIn("作者：作者甲", document.text)
        self.assertIn("发布时间：2026-08-23", document.text)
        self.assertIn("## 核心内容", document.text)
        self.assertNotIn("版权和推荐内容", document.text)

    def test_generic_article_uses_article_element_instead_of_page_chrome(self):
        body = "Generic article content with enough detail for extraction. " * 6
        html = f"""
        <html><head><title>Readable page</title></head><body>
          <header>Global navigation</header>
          <article><h1>Article heading</h1><p>{body}</p></article>
          <aside>Unrelated recommendations</aside>
        </body></html>
        """
        document = extract_article_html(html, url="https://example.com/story")
        self.assertIn("Article heading", document.text)
        self.assertNotIn("Unrelated recommendations", document.text)

    def test_short_wechat_response_has_actionable_fallback(self):
        with self.assertRaisesRegex(UrlDocumentError, "微信中复制正文"):
            extract_article_html(
                "<html><body>环境异常，请稍后重试</body></html>",
                url="https://mp.weixin.qq.com/s/blocked",
            )


if __name__ == "__main__":
    unittest.main()
