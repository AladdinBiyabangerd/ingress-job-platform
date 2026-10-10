import unittest

from worker.techstack import az_market_relevant, foreign_locked_remote


class AzMarketRemoteTest(unittest.TestCase):
    def test_canada_remote_place_is_locked(self):
        self.assertTrue(foreign_locked_remote("Backend Engineer", "Remote, Canada", ""))
        self.assertFalse(
            az_market_relevant(
                "Backend Engineer",
                "Remote, Canada",
                "Fully remote role.",
                remote=True,
                relocation=False,
            )
        )

    def test_us_only_and_residency_lock(self):
        self.assertTrue(
            foreign_locked_remote(
                "Staff Engineer",
                "Remote",
                "Candidates must be located in the United States.",
            )
        )
        self.assertTrue(foreign_locked_remote("Designer", "US Remote", ""))
        self.assertTrue(foreign_locked_remote("SRE", "Remote (UK)", "UK-only remote."))

    def test_toronto_office_as_remote_place_is_locked(self):
        self.assertTrue(foreign_locked_remote("Python Developer", "Toronto, Canada", ""))

    def test_worldwide_and_emea_stay(self):
        self.assertFalse(
            foreign_locked_remote("Backend", "Remote, Worldwide", "Work from anywhere.")
        )
        self.assertFalse(foreign_locked_remote("Backend", "Remote EMEA", ""))
        self.assertTrue(
            az_market_relevant(
                "Backend",
                "Remote",
                "This is a fully remote role. Work from anywhere.",
                remote=True,
                relocation=False,
            )
        )

    def test_plain_remote_without_geo_stays(self):
        self.assertFalse(foreign_locked_remote("Go Engineer", "Remote", "Fully remote role."))
        self.assertTrue(
            az_market_relevant(
                "Go Engineer",
                "Remote",
                "Fully remote role.",
                remote=True,
                relocation=False,
            )
        )

    def test_azerbaijan_signal_keeps_ad(self):
        self.assertTrue(
            az_market_relevant(
                "Frontend",
                "Remote, Baku",
                "Remote across Azerbaijan.",
                remote=True,
                relocation=False,
            )
        )

    def test_relocation_to_canada_stays(self):
        self.assertTrue(
            az_market_relevant(
                "Backend Engineer",
                "Toronto, Canada",
                "Visa sponsorship and relocation package.",
                remote=False,
                relocation=True,
            )
        )
        # Country-scoped remote is never saved by a relocation keyword (H-1B noise).
        self.assertFalse(
            az_market_relevant(
                "Backend Engineer",
                "Remote, Canada",
                "Relocation support available.",
                remote=True,
                relocation=True,
            )
        )

    def test_emea_in_title_does_not_unlock_germany_remote(self):
        self.assertTrue(
            foreign_locked_remote(
                "Customer Success Application Engineer (EMEA)",
                "Remote (Germany)",
                "Hybrid role supporting EMEA customers.",
            )
        )
        self.assertFalse(
            az_market_relevant(
                "Customer Success Application Engineer (EMEA)",
                "Remote (Germany)",
                "Hybrid role supporting EMEA customers.",
                remote=True,
                relocation=False,
            )
        )

    def test_us_remote_not_saved_by_h1b_keyword(self):
        text = (
            "Remote (United States). H-1B transfer candidates are encouraged to apply. "
            "We sponsor visas for eligible US workers."
        )
        self.assertFalse(
            az_market_relevant(
                "Senior Full Stack Software Engineer (Java)",
                "Remote (United States)",
                text,
                remote=True,
                relocation=True,
            )
        )

    def test_berlin_domestic_reloc_assistance_rejected(self):
        text = (
            "Join our Berlin team. Benefits include club subsidy, Kita placement, "
            "relocation assistance, subsidised office lunches."
        )
        self.assertFalse(
            az_market_relevant(
                "Senior CRM Administrator",
                "Berlin",
                text,
                remote=False,
                relocation=True,
            )
        )

    def test_tokyo_visa_relocation_kept(self):
        text = (
            "Tokyo office role. Japan Relocation Support: Visa sponsorship, "
            "flight ticket support, and housing allowance."
        )
        self.assertTrue(
            az_market_relevant(
                "Platform Engineer",
                "Tokyo",
                text,
                remote=False,
                relocation=True,
            )
        )

    def test_remote_us_state_abbrev_locked(self):
        self.assertTrue(foreign_locked_remote("Security Engineer", "Remote - MA", ""))
        self.assertFalse(
            az_market_relevant(
                "Sr Offensive AI Security Engineer II",
                "Remote - MA",
                "US remote role.",
                remote=True,
                relocation=False,
            )
        )

    def test_us_based_employees_comp_boilerplate_does_not_lock(self):
        text = (
            "Fully remote. Work from anywhere. "
            "For US-based employees, the cash compensation range for this role is $150k. "
            "401k retirement plan + company match (US only)."
        )
        self.assertFalse(foreign_locked_remote("Software Architect", "", text))
        self.assertTrue(
            az_market_relevant(
                "Software Architect",
                "",
                text,
                remote=True,
                relocation=False,
            )
        )

    def test_emea_plus_malta_city_locked(self):
        self.assertTrue(
            foreign_locked_remote(
                "Principal Product Manager",
                "Remote Roles - EMEA; Sliema, Malta",
                "Trading tools.",
            )
        )

    def test_amer_in_title_locked(self):
        self.assertTrue(
            foreign_locked_remote("OrioleDB Deployment Engineer (AMER)", "", "Postgres role.")
        )

    def test_california_remote_not_opened_by_company_worldwide(self):
        text = (
            "Candidates in other locations (US based) will be considered. "
            "More than 20,000 organizations worldwide rely on Databricks. "
            "Must have an active or current US GOV Secret clearance eligibility."
        )
        self.assertTrue(
            foreign_locked_remote(
                "Staff Security Engineer, Incident Response",
                "Remote - California",
                text,
            )
        )
        self.assertFalse(
            az_market_relevant(
                "Staff Security Engineer, Incident Response",
                "Remote - California",
                text,
                remote=True,
                relocation=False,
            )
        )

    def test_us_based_locks_plain_remote_place(self):
        self.assertTrue(
            foreign_locked_remote(
                "Security Engineer",
                "Remote",
                "Candidates in other locations (US based) will be considered.",
            )
        )

    def test_tel_aviv_hybrid_is_not_kept(self):
        from worker.techstack import foreign_office_without_offer

        text = "Software Engineer in our product team.\n#LI-Hybrid\n"
        self.assertTrue(foreign_office_without_offer("Software Engineer", "Tel Aviv", text))
        self.assertFalse(
            az_market_relevant(
                "Software Engineer",
                "Tel Aviv",
                text,
                remote=False,
                relocation=False,
            )
        )

    def test_germany_wide_remote_is_locked(self):
        text = (
            "You work remotely (Germany-wide), with offices in Hamburg, Berlin or Munich. "
            "German is a big plus."
        )
        self.assertTrue(
            foreign_locked_remote(
                "Senior Product Designer",
                "Remote",
                text,
            )
        )
        self.assertFalse(
            az_market_relevant(
                "Senior Product Designer",
                "Remote; Hamburg; Berlin; München",
                text,
                remote=True,
                relocation=False,
            )
        )

    def test_cincinnati_onsite_remote_possible_not_kept(self):
        text = (
            "Across both on-site and remote/office phases of the project lifecycle. "
            "Lead software commissioning at customer sites. "
            "Own full-scope installation including wiring and physical installation."
        )
        self.assertTrue(foreign_locked_remote("Software Deployment Engineer", "Cincinnati", text))
        self.assertFalse(
            az_market_relevant(
                "Software Deployment Engineer",
                "Cincinnati",
                text,
                remote=True,
                relocation=False,
            )
        )

    def test_chile_residency_spanish_locked(self):
        text = (
            "Modalidad: 100% remoto, los candidatos deben residir en Chile para postular."
        )
        self.assertTrue(foreign_locked_remote("DevSecOps Senior", "", text))
        self.assertFalse(
            az_market_relevant(
                "DevSecOps Senior",
                "",
                text,
                remote=True,
                relocation=False,
            )
        )

    def test_chile_nationality_and_calendar_locked(self):
        text = (
            "Nacionalidad Chilena (excluyente). "
            "Horario: De 09:00 a 18:00 horas, horario de Chile. "
            "Feriados de Chile. Pago USD."
        )
        self.assertTrue(foreign_locked_remote("Senior iOS Developer", "", text))
        self.assertFalse(
            az_market_relevant(
                "Senior Outsystems QA con Inglés y Español",
                "",
                text,
                remote=True,
                relocation=False,
            )
        )

    def test_latam_based_talent_locked(self):
        text = (
            "TopTalent from LatAm. We need a Senior DevOps Engineer, "
            "based in Latin America, available to work remotely."
        )
        self.assertTrue(foreign_locked_remote("Senior DevOps Engineer", "", text))
        self.assertFalse(
            az_market_relevant(
                "Senior DevOps Engineer",
                "",
                text,
                remote=True,
                relocation=False,
            )
        )

    def test_korea_location_line_locked(self):
        text = (
            "Location: South Korea | Remote\n"
            "We are looking for Image Quality Evaluators based in South Korea. "
            "Currently residing in South Korea."
        )
        self.assertTrue(foreign_locked_remote("AI Trainer Image QA Evaluator", "", text))
        self.assertFalse(
            az_market_relevant(
                "AI Trainer Image QA Evaluator",
                "",
                text,
                remote=True,
                relocation=False,
            )
        )

    def test_title_na_suffix_and_brasil_locked(self):
        self.assertTrue(
            foreign_locked_remote("Senior Forward Deployed Engineer - NA", "", "Fully remote.")
        )
        self.assertTrue(
            foreign_locked_remote(
                "Desarrollador/a Outsystems en Brasil con Inglés",
                "",
                "Modalidad: 100% remoto. Calendario laboral de Chile.",
            )
        )

    def test_cet_timezone_band_locked(self):
        text = (
            "HYBRID (Berlin) or REMOTE (CET ±2h). "
            "We're not able to offer relocation or visa sponsorship. "
            "Fully remote within CET ±2h."
        )
        self.assertTrue(foreign_locked_remote("Lead Platform Engineer", "", text))
        self.assertFalse(
            az_market_relevant(
                "Lead Platform Engineer",
                "",
                text,
                remote=True,
                relocation=False,
            )
        )

    def test_india_rupee_stipend_locked(self):
        text = (
            "Mode: Remote. Stipend: Rs 8,000 per month. "
            "Final-year B.Tech/B.E. students."
        )
        self.assertTrue(
            foreign_locked_remote("AI/ML Intern - Python, LLM Fine-Tuning", "", text)
        )

    def test_country_list_hire_from_does_not_lock(self):
        # Marketplace blurbs listing many hire-from countries must stay open.
        text = (
            "Remote marketplace connecting developers from 75+ countries across "
            "Europe, Latin America, North America (the U.S. and Canada), selected "
            "countries in Asia (Japan, Singapore, South Korea)."
        )
        self.assertFalse(
            foreign_locked_remote("Senior .NET Full-stack Developer", "", text)
        )
        self.assertTrue(
            az_market_relevant(
                "Senior .NET Full-stack Developer",
                "",
                text,
                remote=True,
                relocation=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
