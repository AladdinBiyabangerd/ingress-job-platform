import unittest

from worker.techstack import MAX_STACK, extract_stack, is_tech_job


class JavaDetection(unittest.TestCase):
    def test_case_insensitive(self):
        for t in ("Senior JAVA developer", "we write java 17", "Java/Kotlin"):
            self.assertIn("Java", extract_stack(t), t)

    def test_javascript_is_not_java(self):
        for t in ("JavaScript", "JAVASCRIPT", "Java Script", "java-script"):
            self.assertNotIn("Java", extract_stack(t), t)

    def test_core_language_survives_truncation(self):
        text = ("Docker Kubernetes AWS GCP Terraform Kafka Redis PostgreSQL MySQL "
                "MongoDB React Angular Jenkins Ansible Helm " * 3) + " and java"
        stack = extract_stack(text)
        self.assertLessEqual(len(stack), MAX_STACK)
        self.assertIn("Java", stack)

    def test_core_language_survives_tag_truncation(self):
        tags = ["docker", "kubernetes", "aws", "gcp", "terraform", "kafka", "redis",
                "postgresql", "mysql", "mongodb", "react", "angular", "jenkins", "java"]
        stack = extract_stack("", tags=tags)
        self.assertLessEqual(len(stack), MAX_STACK)
        self.assertIn("Java", stack)

    def test_java_word_does_not_make_sales_tech(self):
        self.assertFalse(is_tech_job("Sales Manager", "sell to java shops"))


class JavaRulesStillReject(unittest.TestCase):
    """Java ads from Polish boards are remote-within-Poland; they must stay out."""

    def test_country_locked_remote_java_rejected(self):
        from worker.techstack import az_market_relevant
        self.assertFalse(az_market_relevant(
            "Senior Java Developer", "Poland - Remote",
            "100% remote, candidates must be based in Poland. B2B.", remote=True, relocation=False))

    def test_foreign_office_java_rejected(self):
        from worker.techstack import az_market_relevant
        self.assertFalse(az_market_relevant(
            "Java Developer", "Krakow, Poland", "Office in Krakow, 5 days a week.",
            remote=False, relocation=False))

    def test_worldwide_remote_java_kept(self):
        from worker.techstack import az_market_relevant
        self.assertTrue(az_market_relevant(
            "Senior Java Engineer", "Remote - Worldwide", "Work from anywhere.",
            remote=True, relocation=False))


if __name__ == "__main__":
    unittest.main()
