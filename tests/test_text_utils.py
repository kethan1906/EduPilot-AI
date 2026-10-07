import unittest

from utils.text_utils import chunk_text, clean_text


class CleanTextTests(unittest.TestCase):
    def test_collapses_whitespace_and_pdf_line_breaks(self):
        self.assertEqual(clean_text("  Hello \n\n world\t again  "), "Hello world again")

    def test_empty_and_whitespace_only(self):
        self.assertEqual(clean_text(""), "")
        self.assertEqual(clean_text(" \n\t "), "")


class ChunkTextTests(unittest.TestCase):
    def test_short_text_is_one_chunk(self):
        self.assertEqual(chunk_text("a b c", chunk_size=10, overlap=2), ["a b c"])

    def test_empty_text_gives_no_chunks(self):
        self.assertEqual(chunk_text("", chunk_size=10, overlap=2), [])

    def test_chunks_overlap_by_requested_words(self):
        words = [f"w{i}" for i in range(25)]
        chunks = chunk_text(" ".join(words), chunk_size=10, overlap=3)
        self.assertEqual(chunks[0].split(), words[0:10])
        self.assertEqual(chunks[1].split(), words[7:17])   # starts 3 words before end of chunk 0
        self.assertEqual(chunks[2].split(), words[14:24])
        self.assertEqual(chunks[3].split(), words[21:25])
        self.assertEqual(chunks[0].split()[-3:], chunks[1].split()[:3])

    def test_every_word_is_covered_and_no_chunk_exceeds_size(self):
        words = [f"w{i}" for i in range(1000)]
        chunks = chunk_text(" ".join(words), chunk_size=450, overlap=75)
        self.assertTrue(all(len(c.split()) <= 450 for c in chunks))
        seen = set()
        for c in chunks:
            seen.update(c.split())
        self.assertEqual(seen, set(words))

    def test_exact_chunk_size_terminates_with_single_chunk(self):
        text = " ".join(f"w{i}" for i in range(450))
        self.assertEqual(len(chunk_text(text)), 1)

    def test_invalid_parameters_raise(self):
        with self.assertRaises(ValueError):
            chunk_text("a b c", chunk_size=5, overlap=5)   # would loop forever
        with self.assertRaises(ValueError):
            chunk_text("a b c", chunk_size=0, overlap=0)
        with self.assertRaises(ValueError):
            chunk_text("a b c", chunk_size=5, overlap=-1)


if __name__ == "__main__":
    unittest.main()
