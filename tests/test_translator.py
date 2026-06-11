# -*- coding: utf-8 -*-
"""Testes do pipeline de tradução (sem rede: usa clientes falsos).

Rodar a partir da pasta do projeto:  python -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import translator as tr  # noqa: E402


class FakeClient:
    """Cliente falso: devolve respostas programadas, registra chamadas."""

    def __init__(self, reply="— Olá.\n\nEla sorriu."):
        self.reply = reply
        self.calls = []

    def chat_stream(self, model, system, user, **kw):
        self.calls.append((system, user))
        yield self.reply


class TestChunking(unittest.TestCase):
    def test_paragrafos_separados_por_linha_em_branco(self):
        chunks = tr.chunk_text("A。\n\nB。\n\nC。", max_chars=1800)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].count("\n\n"), 2)

    def test_sem_perda_de_texto(self):
        jp = ("彼女は静かに微笑んだ。" * 30 + "\n\n") * 8
        chunks = tr.chunk_text(jp, max_chars=400)
        self.assertTrue(all(len(c) <= 401 for c in chunks))
        self.assertEqual("".join(c.replace("\n", "") for c in chunks),
                         jp.replace("\n", ""))

    def test_sanitize_runs_de_pontuacao(self):
        s = tr.sanitize_source("黙った。" + "…" * 300 + "言った。")
        self.assertNotIn("…" * 7, s)
        self.assertIn("……", s)


class TestPostprocess(unittest.TestCase):
    def test_interjeicao_romaji(self):
        pp = tr.postprocess_translation
        self.assertEqual(pp('「n?」 disse.', "Português (BR)"), '“Hum?” disse.')
        self.assertEqual(pp('— N?', "Português (BR)"), '— Hum?')
        self.assertEqual(pp('「un」', "Inglês"), '“Yeah”')

    def test_nao_mexe_em_palavras_reais(self):
        pp = tr.postprocess_translation
        self.assertEqual(pp('"Sim" disse.', "Português (BR)"), '"Sim" disse.')

    def test_vazamento_de_marcadores(self):
        out = tr.postprocess_translation(
            "Texto.\n[Final do contexto]\nMais.", "Português (BR)")
        self.assertNotIn("Final do contexto", out)

    def test_loop_de_repeticao_colapsado(self):
        loop = "Mesma frase.\n\n" * 50 + "Fim."
        out = tr.postprocess_translation(loop, "Português (BR)")
        self.assertEqual(out.count("Mesma frase."), 2)
        self.assertIn("Fim.", out)


class TestPrompts(unittest.TestCase):
    def test_estilo_e_regras(self):
        p = tr.build_system_prompt("Português (BR)", "Completo", "Japonês")
        for marca in ("fan translator", "ZERO Japanese script",
                      "STRUCTURE RULE", "Hum?"):
            self.assertIn(marca, p)

    def test_glossario_e_memoria(self):
        p = tr.build_system_prompt("Português (BR)", "Completo", "Japonês",
                                   "X = Y | mulher", "RESUMO")
        self.assertIn("GLOSSARY", p)
        self.assertIn("X = Y | mulher", p)
        self.assertIn("STORY CONTEXT", p)

    def test_niveis(self):
        alta = tr.build_system_prompt("Português (BR)", "Dinamização alta",
                                      "Japonês")
        self.assertIn("HEAVILY", alta)
        completo = tr.build_system_prompt("Português (BR)", "Completo",
                                          "Japonês")
        self.assertNotIn("condense the translation", completo)


class TestTranslateChapter(unittest.TestCase):
    def test_fluxo_completo(self):
        c = FakeClient("「n?」\n\nEla se virou.")
        out = tr.translate_chapter(c, "m", "「ん？」\n\n彼女は振り向いた。",
                                   "Português (BR)", "Completo")
        self.assertEqual(out, "“Hum?”\n\nEla se virou.")

    def test_memoria_e_glossario_no_system(self):
        c = FakeClient()
        tr.translate_chapter(c, "m", "テスト", "Português (BR)", "Completo",
                             glossary="A = B", memory="HISTÓRIA: x")
        system = c.calls[0][0]
        self.assertIn("A = B", system)
        self.assertIn("HISTÓRIA: x", system)


class TestMemory(unittest.TestCase):
    def test_update_e_protecao(self):
        mem = "PERSONAGENS: A\nHISTÓRIA: longa o suficiente para o teste."
        ok = tr.update_memory(FakeClient("PERSONAGENS: A, B\nHISTÓRIA: nova"),
                              "m", mem, "Cap 2", "texto")
        self.assertIn("B", ok)
        ruim = tr.update_memory(FakeClient("x"), "m", mem, "Cap 3", "texto")
        self.assertEqual(ruim, mem)  # resposta minúscula rejeitada


class TestReview(unittest.TestCase):
    def test_aceita_revisao_boa(self):
        texto = "Frase um pouco estranha aqui.\n\nOutra frase do texto."
        c = FakeClient("Frase mais natural aqui.\n\nOutra frase do texto.")
        out = tr.review_translation(c, "m", texto, "Português (BR)")
        self.assertIn("mais natural", out)

    def test_rejeita_revisao_destrutiva(self):
        texto = "Par 1.\n\nPar 2.\n\nPar 3.\n\nPar 4." * 3
        c = FakeClient("curto")  # encolheu demais
        out = tr.review_translation(c, "m", texto, "Português (BR)")
        self.assertEqual(out, texto)


class TestGlossaryLearning(unittest.TestCase):
    # obra fictícia: 月森アヤメ (personagem), 星霜剣記 (título)
    SRC = [("c1", "俺、月森アヤメは学生だ。" + "話の続き。" * 50)]
    DST = [("c1", "Eu, Ayame Tsukimori, sou estudante. "
                  + "Continuação da história. " * 50)]

    def test_extrai_e_valida(self):
        c = FakeClient("1. **月森アヤメ** = Ayame Tsukimori\n"
                       "学生 = Coisa Inventada")
        pares = tr.learn_glossary(c, "m", self.SRC, self.DST,
                                  "Português (BR)")
        d = dict(pares)
        self.assertEqual(d.get("月森アヤメ"), "Ayame Tsukimori")
        self.assertNotIn("学生", d)  # tradução não existe no texto -> rejeita

    def test_nao_duplica_existentes(self):
        c = FakeClient("月森アヤメ = Ayame Tsukimori")
        pares = tr.learn_glossary(c, "m", self.SRC, self.DST,
                                  "Português (BR)",
                                  existing="月森アヤメ = Ayame Tsukimori")
        self.assertEqual(pares, [])


class TestImageMarkers(unittest.TestCase):
    def test_prompt_instrui_preservacao(self):
        p = tr.build_system_prompt("Português (BR)", "Completo", "Japonês")
        self.assertIn("IMAGE MARKERS", p)
        self.assertIn("⟦IMG3⟧", p)

    def test_marcador_preservado_no_fluxo(self):
        c = FakeClient("Texto traduzido.\n\n⟦IMG1⟧\n\nMais texto.")
        out = tr.translate_chapter(c, "m", "本文。\n\n⟦IMG1⟧\n\n続き。",
                                   "Português (BR)", "Completo")
        self.assertIn("⟦IMG1⟧", out)

    def test_marcador_perdido_e_restaurado(self):
        # modelo "esqueceu" o marcador: rede de segurança devolve ao fim
        c = FakeClient("Texto traduzido sem o marcador.")
        out = tr.translate_chapter(c, "m", "本文。\n\n⟦IMG7⟧\n\n続き。",
                                   "Português (BR)", "Completo")
        self.assertIn("⟦IMG7⟧", out)

    def test_sanitize_e_postprocess_nao_destroem_marcador(self):
        s = tr.sanitize_source("⟦IMG2⟧\n\n" + "…" * 300)
        self.assertIn("⟦IMG2⟧", s)
        out = tr.postprocess_translation("⟦IMG2⟧\n\nTexto.", "Português (BR)")
        self.assertIn("⟦IMG2⟧", out)


class TestNameConsistency(unittest.TestCase):
    def test_deteccao_via_glossario(self):
        texts = ["Ayame Tsukimori sorriu. Tsukimori Ayame correu.",
                 "Ayame Tsukimori voltou."]
        f = tr.find_name_inconsistencies(texts,
                                         "月森アヤメ = Ayame Tsukimori")
        assert any(x["de"] == "Tsukimori Ayame"
                   and x["para"] == "Ayame Tsukimori"
                   and x["fonte"] == "glossário" for x in f), f

    def test_deteccao_generica_maioria_vence(self):
        texts = ["Ren Kurotsuki atacou. Ren Kurotsuki venceu.",
                 "Kurotsuki Ren caiu."]
        f = tr.find_name_inconsistencies(texts)
        m = [x for x in f if x["para"] == "Ren Kurotsuki"]
        self.assertTrue(m and m[0]["de"] == "Kurotsuki Ren")

    def test_sem_falso_positivo(self):
        f = tr.find_name_inconsistencies(
            ["Ela correu pela rua. O vento soprava forte."])
        self.assertEqual(f, [])

    def test_aplicacao(self):
        out = tr.apply_name_mapping(
            "Tsukimori Ayame chegou.", {"Tsukimori Ayame": "Ayame Tsukimori"})
        self.assertEqual(out, "Ayame Tsukimori chegou.")


class TestSuggestGlossary(unittest.TestCase):
    TEXTO = "俺、月森アヤメは『星霜剣記』を読んでいた。"

    def test_valida_e_limpa(self):
        c = FakeClient("1. **月森アヤメ** = Ayame Tsukimori\n"
                       "存在しない = Inventado")
        pares = tr.suggest_glossary(c, "m", self.TEXTO, "Português (BR)")
        d = dict(pares)
        self.assertEqual(d.get("月森アヤメ"), "Ayame Tsukimori")
        self.assertNotIn("存在しない", d)  # não está no texto -> descarta

    def test_nao_duplica_existentes(self):
        c = FakeClient("月森アヤメ = Ayame Tsukimori")
        pares = tr.suggest_glossary(c, "m", self.TEXTO, "Português (BR)",
                                    existing="月森アヤメ = X")
        self.assertEqual(pares, [])


class TestExtractorMarkers(unittest.TestCase):
    def test_strip_image_markers(self):
        from extractor import strip_image_markers
        self.assertEqual(strip_image_markers("A.\n\n⟦IMG1⟧\n\nB."),
                         "A.\n\nB.")


if __name__ == "__main__":
    unittest.main()
