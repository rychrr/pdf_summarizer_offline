import unittest
from unittest.mock import patch, MagicMock
import summarizer_pipeline as sp
import os

class TestSummarizerPipeline(unittest.TestCase):

    def setUp(self):
        self.sample_text = "This is a test document. It has multiple sentences."
        self.pdf_path = "tests/sample.pdf"
        self.ocr_path = "tests/sample_ocr.txt"
        self.prompt_template = "Summarize the following:\n{text}"

    def test_clean_text_removes_non_ascii_and_multiple_spaces(self):
        dirty = "This  is   a\ttest \u2014 document."
        cleaned = sp.clean_text(dirty)
        self.assertEqual(cleaned, "This is a test document.")

    def test_hash_line(self):
        self.assertEqual(sp.hash_line("Hello"), sp.hash_line("hello "))

    def test_split_text_smart(self):
        long_text = "word " * 2100
        chunks = sp.split_text_smart(long_text.strip())
        self.assertTrue(len(chunks) >= 1)
        self.assertTrue(all(len(chunk.split()) <= 2000 for chunk in chunks))

    @patch("summarizer_pipeline.fitz.open")
    def test_extract_text_from_pdf(self, mock_fitz):
        mock_doc = [MagicMock(get_text=MagicMock(return_value="Page content")) for _ in range(2)]
        mock_fitz.return_value = mock_doc
        result = sp.extract_text_from_pdf("dummy.pdf")
        self.assertIn("Page 1", result)
        self.assertIn("Page 2", result)

    @patch("summarizer_pipeline.convert_from_path")
    @patch("summarizer_pipeline.pytesseract.image_to_string")
    def test_extract_text_from_images(self, mock_ocr, mock_convert):
        mock_convert.return_value = [MagicMock()] * 2
        mock_ocr.return_value = "Detected text"
        result = sp.extract_text_from_images("dummy.pdf")
        self.assertIn("Detected text", result)

    def test_read_prompt_template(self):
        path = "tests/test_prompt.txt"
        with open(path, 'w', encoding='utf-8') as f:
            f.write("Summarize:\n{text}")
        content = sp.read_prompt_template(path)
        self.assertIn("{text}", content)
        os.remove(path)

    @patch("summarizer_pipeline.requests.post")
    def test_query_llama3_success(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"response": "Mock summary"}
        result = sp.query_llama3("text")
        self.assertEqual(result, "Mock summary")

    @patch("summarizer_pipeline.query_llama3")
    def test_summarize_chunk_with_id(self, mock_llm):
        mock_llm.return_value = "Summary"
        index, summary = sp.summarize_chunk_with_id(1, "Text", self.prompt_template, "model")
        self.assertEqual(index, 1)
        self.assertEqual(summary, "Summary")

if __name__ == '__main__':
    unittest.main()
