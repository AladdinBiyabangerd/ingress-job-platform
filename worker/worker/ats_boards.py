"""Employer job boards read through public ATS APIs, grouped by region.

Plain data, no imports: catalog.py builds the source rows from it and
connectors/ats.py builds one connector per group. Every slug was checked on
2026-10-05: the board answered, robots.txt allowed it and it listed tech roles.
Companies that hire remotely or sponsor visas/relocation were preferred.
Each group reads at most ATS_MAX_BOARDS boards per pass; larger groups rotate.
"""

ATS_MAX_BOARDS = 12

# (source name, ATS, short Azerbaijani region label, board slugs)
GROUPS: list[tuple[str, str, str, tuple[str, ...]]] = [
    # ---- Greenhouse (boards-api.greenhouse.io)
    ("Greenhouse boards (UK & Ireland)", "greenhouse", "Böyük Britaniya və İrlandiya", (
        "monzo", "deliveroo", "gocardless", "graphcore", "intercom", "tide", "tines", "cleo",
        "stabilityai", "sumup", "canonical")),
    ("Greenhouse boards (DACH)", "greenhouse", "Almaniya, Avstriya, İsveçrə", (
        "n26", "hellofresh", "getyourguide", "celonis", "helsing", "contentful", "trivago",
        "commercetools", "parloa", "raisin", "scandit", "solarisbank", "staffbase", "bitpanda",
        "gostudent")),
    ("Greenhouse boards (Benelux & France)", "greenhouse", "Benilüks və Fransa", (
        "adyen", "elastic", "doctolib", "algolia", "catawiki", "dataiku", "mirakl")),
    ("Greenhouse boards (Nordics & Baltics)", "greenhouse", "Skandinaviya və Baltikyanı", (
        "wolt", "oura", "relex", "truecaller", "veriff", "mentimeter", "trustpilot", "yousician")),
    ("Greenhouse boards (Southern & Eastern Europe)", "greenhouse", "Cənubi və Şərqi Avropa", (
        "cabify", "feedzai", "swordhealth", "typeform", "wallapop")),
    ("Greenhouse boards (US West)", "greenhouse", "ABŞ qərb sahili", (
        "affirm", "coinbase", "instacart", "reddit", "samsara", "mercury", "tailscale", "twilio",
        "webflow", "pinterest", "databricks", "stripe", "airbnb", "discord", "dropbox", "vercel",
        "planetscale", "calendly", "nextdoor", "gusto", "cloudflare", "figma", "anthropic", "lyft")),
    ("Greenhouse boards (US East)", "greenhouse", "ABŞ şərq sahili", (
        "datadog", "mongodb", "gitlab", "toast", "zocdoc", "justworks", "duolingo", "squarespace",
        "klaviyo", "peloton", "oscar", "betterment", "attentive", "yext", "grafanalabs")),
    ("Greenhouse boards (Canada)", "greenhouse", "Kanada", (
        "d2l", "faire", "geotab", "hootsuite", "ritual", "shakepay")),
    ("Greenhouse boards (Latin America)", "greenhouse", "Latın Amerikası", (
        "gympass", "clara", "ebanx", "quintoandar", "stone", "vtex", "wizeline")),
    ("Greenhouse boards (India)", "greenhouse", "Hindistan", (
        "druva", "hackerrank", "inmobi", "observeai", "slice", "razorpaysoftwareprivatelimited")),
    ("Greenhouse boards (Southeast Asia)", "greenhouse", "Cənub-Şərqi Asiya", (
        "thunes", "xendit", "okx", "thoughtworks")),
    ("Greenhouse boards (Japan & Korea)", "greenhouse", "Yaponiya və Koreya", (
        "paypay", "coupang", "daangn", "krafton", "moloco", "sendbird")),
    ("Greenhouse boards (Australia & NZ)", "greenhouse", "Avstraliya və Yeni Zelandiya", (
        "cultureamp", "buildkite", "eucalyptus", "pushpay", "octopusdeploy")),
    ("Greenhouse boards (Middle East & Africa)", "greenhouse", "Yaxın Şərq və Afrika", (
        "careem", "tamara", "bybit", "ozow", "wizinc", "jfrog", "axonius", "payoneer", "riskified",
        "melio", "similarweb", "taboola", "catonetworks", "transmitsecurity", "yotpo")),
    # ---- Lever (api.lever.co)
    ("Lever boards (Europe)", "lever", "Avropa", (
        "spotify", "qonto", "swile", "aircall", "zopa", "farfetch", "malt", "blablacar",
        "contentsquare", "pipedrive", "lodgify", "jobandtalent", "dreamgames", "peakgames",
        "trendyol")),
    ("Lever boards (Americas)", "lever", "Şimali və Latın Amerikası", (
        "palantir", "toptal", "anchorage", "olo", "fullscript", "outreach", "jumpcloud", "ro",
        "zoox", "wattpad", "relay", "dlocal", "kavak")),
    ("Lever boards (India)", "lever", "Hindistan", (
        "meesho", "paytm", "zeta", "mindtickle", "fampay")),
    ("Lever boards (Asia-Pacific)", "lever", "Şərqi və Cənub-Şərqi Asiya, Avstraliya", (
        "woven-by-toyota", "crypto", "lalamove", "nium", "ninjavan", "binance", "deputy",
        "immutable")),
    # ---- Teamtailor ({company}.teamtailor.com/jobs.rss)
    ("Teamtailor boards (Nordics)", "teamtailor", "Skandinaviya", (
        "tibber", "polestar", "anyfin", "instabee", "templafy", "detectify", "doktor", "bannerflow",
        "brite", "lunar", "storytel", "naturalcycles", "fishbrain", "quinyx", "hedvig")),
    ("Teamtailor boards (Rest of Europe)", "teamtailor", "Baltikyanı və digər Avropa", (
        "starship", "carvertical", "seedtag")),
]
