from __future__ import annotations

from dataclasses import dataclass
import unittest
from unittest.mock import patch

from app_settings import resolve_settings
from sources import (
    Material,
    SourceError,
    classify_url,
    detect_language,
    load_text,
    load_url,
    looks_like_transcript,
    material_task_config,
    suggested_language,
)
from youtube_documents import (
    YouTubeDocumentError,
    _map_error,
    extract_video_id,
    transcript_to_markdown,
)


@dataclass
class Snippet:
    text: str
    start: float
    duration: float = 3.0


class YouTubeUrlTests(unittest.TestCase):
    def test_video_id_forms(self):
        cases = {
            "https://www.youtube.com/watch?v=usnVKWJdAaU&t=42s": "usnVKWJdAaU",
            "https://youtu.be/usnVKWJdAaU?is=hYERDaBodz--wCBv": "usnVKWJdAaU",
            "youtu.be/usnVKWJdAaU": "usnVKWJdAaU",
            "https://m.youtube.com/shorts/usnVKWJdAaU": "usnVKWJdAaU",
            "https://www.youtube.com/live/usnVKWJdAaU?feature=share": "usnVKWJdAaU",
            "https://www.youtube.com/embed/usnVKWJdAaU": "usnVKWJdAaU",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(extract_video_id(url), expected)

    def test_non_video_urls_are_rejected(self):
        for url in (
            "https://www.youtube.com/playlist?list=PL123",
            "https://www.youtube.com/watch?v=short",
            "https://example.com/watch?v=usnVKWJdAaU",
        ):
            with self.subTest(url=url):
                self.assertIsNone(extract_video_id(url))

    def test_classify_url(self):
        self.assertEqual(classify_url("https://youtu.be/usnVKWJdAaU"), "youtube")
        self.assertEqual(classify_url("https://www.bilibili.com/video/BV1KvHn6xETv"), "bilibili")
        self.assertEqual(classify_url("https://b23.tv/A21FpZd"), "bilibili")
        self.assertEqual(classify_url("https://mp.weixin.qq.com/s/abc"), "web")


class TranscriptMarkdownTests(unittest.TestCase):
    def test_paragraphs_are_timestamped_and_no_headings_are_invented(self):
        snippets = [Snippet(f"Sentence number {index}.", index * 5.0) for index in range(40)]
        snippets.insert(3, Snippet("[Music]", 14.0))
        text, duration = transcript_to_markdown(
            snippets,
            title="A dispute",
            url="https://www.youtube.com/watch?v=usnVKWJdAaU",
            channel="Some Channel",
            language="en",
            generated=True,
        )
        self.assertTrue(text.startswith("# A dispute\n\n来源：[YouTube · Some Channel]"))
        self.assertIn("英文自动字幕", text)
        self.assertEqual(text.count("\n# "), 0)
        self.assertNotIn("##", text)
        self.assertNotIn("[Music]", text)
        paragraphs = [block for block in text.split("\n\n") if block.startswith("[")]
        self.assertGreaterEqual(len(paragraphs), 3)
        self.assertTrue(paragraphs[0].startswith("[00:00] Sentence number 0."))
        self.assertEqual(duration, 198)

    def test_cjk_captions_join_without_spaces(self):
        text, _ = transcript_to_markdown(
            [Snippet("你好", 0.0), Snippet("世界。", 2.0)],
            title="t",
            url="u",
            channel=None,
            language="zh-Hans",
            generated=False,
        )
        self.assertIn("[00:00] 你好世界。", text)
        self.assertIn("简体中文字幕", text)


class YouTubeErrorMappingTests(unittest.TestCase):
    def test_library_errors_map_to_guidance(self):
        def named(name: str) -> Exception:
            return type(name, (Exception,), {})()

        self.assertEqual(_map_error(named("RequestBlocked")).code, "youtube-blocked")
        self.assertEqual(_map_error(named("IpBlocked")).code, "youtube-blocked")
        self.assertEqual(_map_error(named("TranscriptsDisabled")).code, "youtube-no-captions")
        self.assertEqual(_map_error(named("VideoUnavailable")).code, "youtube-unavailable")
        self.assertEqual(_map_error(named("Something")).code, "youtube-failed")
        self.assertTrue(_map_error(named("RequestBlocked")).hint)


class LoadUrlTests(unittest.TestCase):
    def test_youtube_is_local_only_when_disabled(self):
        with self.assertRaises(SourceError) as caught:
            load_url("https://youtu.be/usnVKWJdAaU", youtube_enabled=False)
        self.assertEqual(caught.exception.code, "youtube-local-only")
        self.assertIn("粘贴", caught.exception.hint)

    def test_bilibili_is_refused_with_next_step(self):
        with self.assertRaises(SourceError) as caught:
            load_url("https://www.bilibili.com/video/BV1KvHn6xETv")
        self.assertEqual(caught.exception.code, "bilibili-unsupported")

    def test_private_hosts_are_still_rejected(self):
        with self.assertRaises(SourceError) as caught:
            load_url("http://localhost:8501/")
        self.assertEqual(caught.exception.code, "invalid-url")

    def test_youtube_document_carries_transcript_material(self):
        from youtube_documents import YouTubeTranscript

        video = YouTubeTranscript(
            text="# T\n\n来源：…\n\n[00:00] Hello.",
            title="T",
            channel="Channel",
            url="https://www.youtube.com/watch?v=usnVKWJdAaU",
            video_id="usnVKWJdAaU",
            language="en",
            generated=True,
            duration_seconds=1479,
        )
        with patch("youtube_documents.fetch_youtube_transcript", return_value=video):
            document = load_url("https://youtu.be/usnVKWJdAaU", youtube_enabled=True)
        self.assertEqual(document.material.kind, "transcript")
        self.assertEqual(document.material.author, "Channel")
        self.assertEqual(document.site, "YouTube · Channel")
        self.assertEqual(document.notices, ("英文自动字幕", "无说话人标注"))
        config = material_task_config(document.material)
        self.assertEqual(config["origin"], "youtube")
        self.assertTrue(config["asr"])
        self.assertEqual(config["duration_seconds"], 1479)

    def test_youtube_errors_become_source_errors(self):
        error = YouTubeDocumentError("blocked", code="youtube-blocked", hint="paste")
        with patch("youtube_documents.fetch_youtube_transcript", side_effect=error):
            with self.assertRaises(SourceError) as caught:
                load_url("https://youtu.be/usnVKWJdAaU", youtube_enabled=True)
        self.assertEqual((caught.exception.code, caught.exception.hint), ("youtube-blocked", "paste"))


class MaterialDetectionTests(unittest.TestCase):
    def test_timestamped_text_is_a_transcript(self):
        text = "\n".join(f"[{index:02d}:00] line {index}" for index in range(12))
        self.assertTrue(looks_like_transcript(text))
        self.assertEqual(load_text(text).material.kind, "transcript")

    def test_caption_fragments_are_a_transcript(self):
        text = "\n".join(f"and then she said {index}" for index in range(60))
        self.assertTrue(looks_like_transcript(text))

    def test_article_is_not_a_transcript(self):
        text = "# 标题\n\n" + "\n\n".join(f"这是第 {index} 段完整的正文，句子结束。" for index in range(20))
        self.assertFalse(looks_like_transcript(text))
        self.assertEqual(load_text(text).material.kind, "article")

    def test_language_detection_and_suggestion(self):
        self.assertEqual(detect_language("这是一个中文句子，用来测试语言识别是否正常工作。"), "zh")
        self.assertEqual(detect_language("This is an English sentence for language detection."), "en")
        english_video = Material(kind="transcript", origin="youtube", language="en")
        chinese_video = Material(kind="transcript", origin="youtube", language="zh")
        article = Material(kind="article", origin="web", language="en")
        self.assertEqual(suggested_language(english_video), "zh")
        self.assertEqual(suggested_language(chinese_video), "source")
        self.assertEqual(suggested_language(article), "source")

    def test_article_material_omits_transcript_fields(self):
        config = material_task_config(Material(kind="article", origin="wechat", language="zh"))
        self.assertEqual(config, {"kind": "article", "origin": "wechat", "language": "zh"})


class SettingsTests(unittest.TestCase):
    def test_unknown_models_fall_back_to_default(self):
        settings = resolve_settings({"DEEPSEEK_MODEL": "deepseek-v4.1-flash-expires-on-0910"})
        self.assertEqual(settings.model, "deepseek-flash")
        self.assertEqual(resolve_settings({"DEEPSEEK_MODEL": "deepseek-v4-pro"}).model, "deepseek-v4-pro")

    def test_youtube_flag_can_be_forced_off(self):
        self.assertFalse(resolve_settings({"YOUTUBE_ENABLED": "false"}).youtube_enabled)

    def test_youtube_defaults_off_on_streamlit_cloud(self):
        with patch("app_settings.running_on_streamlit_cloud", return_value=True):
            self.assertFalse(resolve_settings({}).youtube_enabled)


if __name__ == "__main__":
    unittest.main()
