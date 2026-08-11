from __future__ import annotations

import unittest

from input_documents import InputDocumentError, extract_uploaded_document, filename_stem


class InputDocumentTests(unittest.TestCase):
    def test_filename_stem_removes_extension_and_unsafe_characters(self):
        self.assertEqual(filename_stem('季度报告：最终版?.md', "document"), "季度报告：最终版")

    def test_markdown_upload_preserves_text_and_reports_kind(self):
        document = extract_uploaded_document("reading-notes.md", b"\xef\xbb\xbf# Notes\r\n\r\nText")
        self.assertEqual(document.stem, "reading-notes")
        self.assertEqual(document.kind, "Markdown")
        self.assertEqual(document.pages, 0)
        self.assertEqual(document.text, "# Notes\n\nText")

    def test_txt_upload_is_supported(self):
        document = extract_uploaded_document("transcript.txt", "第一段。".encode("utf-8"))
        self.assertEqual(document.kind, "TXT")
        self.assertEqual(document.text, "第一段。")

    def test_invalid_utf8_is_rejected(self):
        with self.assertRaisesRegex(InputDocumentError, "不是 UTF-8"):
            extract_uploaded_document("legacy.txt", b"\xff\xfe\x00")

    def test_unsupported_extension_is_rejected(self):
        with self.assertRaisesRegex(InputDocumentError, "仅支持"):
            extract_uploaded_document("document.docx", b"content")


if __name__ == "__main__":
    unittest.main()
