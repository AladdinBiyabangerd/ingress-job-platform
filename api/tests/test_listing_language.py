"""listing_language: body beats English titles; persist trusts stored codes."""

import sys
import unittest
from pathlib import Path

_WORKER = Path(__file__).resolve().parents[2] / "worker"
if _WORKER.is_dir() and str(_WORKER) not in sys.path:
    sys.path.insert(0, str(_WORKER))

from worker.listing_language import listing_language, resolve_listing_language


class ListingLanguageTests(unittest.TestCase):
    def test_english_default(self):
        self.assertEqual(
            listing_language(
                "Senior Backend Engineer",
                "We are looking for a Python engineer with AWS experience.",
            ),
            "en",
        )

    def test_azerbaijani_schwa(self):
        self.assertEqual(
            listing_language("Backend mühəndisi", "Şirkətdə Python ilə işləmək tələb olunur."),
            "az",
        )

    def test_russian_cyrillic(self):
        self.assertEqual(
            listing_language(
                "Python Developer",
                "Мы ищем разработчика с опытом работы с Django и PostgreSQL.",
            ),
            "ru",
        )

    def test_ukrainian_letters(self):
        self.assertEqual(
            listing_language(
                "Backend Engineer",
                "Ми шукаємо інженера з досвідом роботи з Python та Kubernetes.",
            ),
            "uk",
        )

    def test_german_english_title(self):
        body = (
            "Die Naturida GmbH ist ein wachsendes Unternehmen. "
            "Wir suchen eine erfahrene Product Managerin für unsere Beauty-Marke. "
            "Die Roadmap verantworten und mit Laboren steuern."
        )
        self.assertEqual(listing_language("Freelance Product Manager (m/w/d)", body), "de")
        # Empty column → infer from body.
        self.assertEqual(resolve_listing_language("", "Freelance Product Manager", body), "de")
        # Persisted facet code is trusted (backfill owns corrections).
        self.assertEqual(resolve_listing_language("en", "Freelance Product Manager", body), "en")
        self.assertEqual(resolve_listing_language("de", "Freelance Product Manager", body), "de")

    def test_french_english_title(self):
        body = (
            "Nous recherchons un développeur pour les projets de l'entreprise. "
            "Vous travaillerez avec notre équipe et votre expérience compte."
        )
        self.assertEqual(listing_language("Software Engineer", body), "fr")

    def test_spanish_english_title(self):
        body = (
            "Buscamos un ingeniero para el equipo de producto. "
            "Experiencia con Python y los requisitos del puesto están en la descripción. "
            "Somos una empresa remota."
        )
        self.assertEqual(listing_language("Software Engineer", body), "es")

    def test_portuguese_english_title(self):
        body = (
            "Procuramos uma pessoa para a vaga de engenharia. "
            "Você vai trabalhar com nosso time. Não é necessário morar em São Paulo. "
            "Experiência com Python pelo menos 3 anos."
        )
        self.assertEqual(listing_language("Software Engineer", body), "pt")

    def test_turkish_english_title(self):
        body = (
            "Şirketimiz için deneyimli bir yazılım mühendisi arıyoruz. "
            "Pozisyon uzaktan çalışma olarak açıktır. Başvuru için CV gönderin."
        )
        self.assertEqual(listing_language("Software Engineer", body), "tr")

    def test_stored_az_trusted(self):
        self.assertEqual(
            resolve_listing_language("az", "Engineer", "We need Python experience."),
            "az",
        )

    def test_single_foreign_word_not_enough(self):
        self.assertEqual(
            listing_language(
                "Backend Engineer",
                "Build APIs with Python. Mentions of die company culture only once.",
            ),
            "en",
        )

    def test_bilingual_weak_margin_falls_back_to_en(self):
        # A few DE stopwords inside an otherwise English JD → not enough margin.
        body = (
            "We are hiring a backend engineer in Berlin. "
            "The role includes und collaboration with die product team. "
            "Strong Python and AWS experience required for this position."
        )
        self.assertEqual(listing_language("Backend Engineer", body), "en")


if __name__ == "__main__":
    unittest.main()
