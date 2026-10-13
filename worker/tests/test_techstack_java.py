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


if __name__ == "__main__":
    unittest.main()
