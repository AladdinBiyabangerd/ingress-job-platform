"""Skills must not be missed because of case / spacing / joined / hyphen / dot
spelling, and the looser matching must not invent skills from plain English."""
import unittest

from worker.techstack import MAX_STACK, extract_stack, find_stack, is_tech_job, stack_from_tags


class SpellingVariantTest(unittest.TestCase):
    def has(self, text, name):
        self.assertIn(name, find_stack(text), text)

    def test_spring_boot_forms(self):
        for v in ("Spring Boot", "spring boot", "SPRING BOOT", "SpringBoot", "springboot",
                  "spring-boot", "Spring-Boot", "spring_boot"):
            self.has(f"Experience with {v} is required.", "Spring")

    def test_js_and_multiword_forms(self):
        for v in ("node.js", "nodejs", "node js", "Node-JS", "NODEJS"):
            self.has(f"Backend in {v}.", "Node.js")
        for v in ("infrastructure as code", "Infrastructure-as-Code"):
            self.has(f"We practise {v} daily.", "Infrastructure as Code")
        self.has("penetration-testing experience", "Penetration Testing")
        self.has("Build AWSLambda functions", "AWS Lambda")
        self.has("You will design an AI agent for support.", "AI Agents")

    def test_case_of_distinctive_names(self):
        for text, name in (("vite and ktor", "Vite"), ("vite and ktor", "Ktor"),
                           ("JUNIT 5 tests", "JUnit"), ("auth via jwt", "JWT"),
                           ("deploy on gcp", "GCP"), ("mqtt devices", "MQTT")):
            self.has(text, name)

    def test_java_versions_and_not_javascript(self):
        for v in ("Java 17", "Java17", "JAVA 21", "java"):
            self.has(f"Modern {v} services", "Java")
        self.assertNotIn("Java", find_stack("JavaScript, Java Script and javascript only"))

    def test_tags_any_separator(self):
        self.assertEqual(stack_from_tags(["spring-boot", "Node_JS", "GitHub-Actions", "react js"]),
                         ["Spring", "Node.js", "GitHub Actions", "React"])
        self.assertEqual(stack_from_tags(["net"]), [])

    def test_tag_spelling_never_widens_tech_gate(self):
        self.assertFalse(is_tech_job("Office Manager", "", ["spring-boot", "node-js", "react-js"]))


class NewJvmSkillsTest(unittest.TestCase):
    def test_resilience4j_feign_flyway(self):
        found = find_stack("Spring Boot, Resilience4j, Feign, Flyway, OpenFeign clients")
        for name in ("Spring", "Resilience4j", "OpenFeign", "Flyway"):
            self.assertIn(name, found)
        self.assertIn("Flyway", find_stack("schema changes via flyway migrations"))
        self.assertIn("Flyway", find_stack("Liquibase/flyway"))


class FalsePositiveTest(unittest.TestCase):
    def test_plain_english_sentences(self):
        noise = (
            "This spring, ai teams met in the park. Boots in spring are great. "
            "We feign surprise when the flyway of migrating birds shifts. "
            "The old swift boat; go to the express train. "
            "The node is a point in the graph. Boot camp in the spring season. "
            "Our core data services team. C is the third letter; R is next. "
            "Express your ideas. Go further. Our snowflake design; the helm of a ship."
        )
        self.assertEqual(find_stack(noise), [])

    def test_integration_and_customer_mentions_are_not_skills(self):
        stack = extract_stack("Typeform integrates with essential tools like Slack, Zapier, and Hubspot. "
                              "Organizations like HubSpot trust us. You will build with React.")
        self.assertNotIn("HubSpot", stack)
        self.assertIn("React", stack)
        self.assertIn("HubSpot", extract_stack("You will integrate with HubSpot APIs using Python."))


class CapRankingTest(unittest.TestCase):
    def test_generic_chips_yield_to_concrete(self):
        text = ("We use LLM and GPT-4 tools, Pub/Sub, A/B testing and incident response. "
                "Java, Kotlin, Spring Boot, JUnit, MySQL, DynamoDB, Kafka, Redis, Docker, "
                "Kubernetes, Argo CD, AWS, Gradle.")
        stack = extract_stack(text)
        self.assertEqual(len(stack), MAX_STACK)
        for name in ("Java", "Kotlin", "Spring", "Kafka", "Redis", "Docker", "Kubernetes"):
            self.assertIn(name, stack)
        self.assertNotIn("Pub/Sub", stack)


if __name__ == "__main__":
    unittest.main()
