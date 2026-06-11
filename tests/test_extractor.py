# -*- coding: utf-8 -*-
"""Testes da extração de livros. EPUB/PDF são pulados se as libs faltarem."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractor import extract_txt  # noqa: E402


class TestTxt(unittest.TestCase):
    def _write(self, content, encoding="utf-8"):
        f = tempfile.NamedTemporaryFile(mode="wb", suffix=".txt",
                                        delete=False)
        f.write(content.encode(encoding))
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_capitulos_japoneses(self):
        path = self._write("第一章 始まり\n" + "本文。" * 30 +
                           "\n第二章 続き\n" + "本文。" * 30)
        chs = extract_txt(path)
        self.assertEqual(len(chs), 2)
        self.assertEqual(chs[0][0], "第一章 始まり")

    def test_shift_jis(self):
        path = self._write("これはテストです。" * 10, encoding="shift_jis")
        chs = extract_txt(path)
        self.assertIn("テスト", chs[0][1])

    def test_sem_marcadores_vira_capitulo_unico(self):
        path = self._write("texto corrido sem capítulos " * 20)
        chs = extract_txt(path)
        self.assertEqual(len(chs), 1)


if __name__ == "__main__":
    unittest.main()
