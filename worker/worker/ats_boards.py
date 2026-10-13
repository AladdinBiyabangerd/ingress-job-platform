"""Employer job boards read through public ATS APIs, grouped by region.

Plain data, no imports: catalog.py builds the source rows from it and
connectors/ats.py builds one connector per group. Every slug was checked on
2026-10-05 (base set) or 2026-10-10 / 2026-10-11 (expansions): the board answered, robots.txt
allowed it and it listed tech roles. Companies that hire remotely or sponsor
visas/relocation were preferred. Each group reads at most ATS_MAX_BOARDS
boards per pass; larger groups rotate.
"""

ATS_MAX_BOARDS = 20

# (source name, ATS, short Azerbaijani region label, board slugs)
GROUPS: list[tuple[str, str, str, tuple[str, ...]]] = [
    # ---- Greenhouse (boards-api.greenhouse.io)
    ("Greenhouse boards (UK & Ireland)", "greenhouse", "Böyük Britaniya və İrlandiya", (
        "monzo", "deliveroo", "gocardless", "graphcore", "intercom", "tide", "tines", "cleo",
        "stabilityai", "sumup", "canonical", "form3")),
    ("Greenhouse boards (DACH)", "greenhouse", "Almaniya, Avstriya, İsveçrə", (
        "n26", "hellofresh", "getyourguide", "celonis", "helsing", "contentful", "trivago",
        "commercetools", "parloa", "raisin", "scandit", "solarisbank", "staffbase", "bitpanda",
        "gostudent", "traderepublicbank", "flix")),
    ("Greenhouse boards (Benelux & France)", "greenhouse", "Benilüks və Fransa", (
        "adyen", "elastic", "doctolib", "algolia", "catawiki", "dataiku", "mirakl")),
    ("Greenhouse boards (Nordics & Baltics)", "greenhouse", "Skandinaviya və Baltikyanı", (
        "wolt", "oura", "relex", "truecaller", "veriff", "mentimeter", "trustpilot", "yousician",
        "neo4j")),
    ("Greenhouse boards (Southern & Eastern Europe)", "greenhouse", "Cənubi və Şərqi Avropa", (
        "cabify", "feedzai", "swordhealth", "typeform", "wallapop", "transfergo", "jetbrains",
        "nix", "bloomreach")),
    ("Greenhouse boards (US West)", "greenhouse", "ABŞ qərb sahili", (
        "affirm", "coinbase", "instacart", "reddit", "samsara", "mercury", "tailscale", "twilio",
        "webflow", "pinterest", "databricks", "stripe", "airbnb", "discord", "dropbox", "vercel",
        "planetscale", "calendly", "nextdoor", "gusto", "cloudflare", "figma", "anthropic", "lyft",
        "robinhood", "asana", "scaleai", "brex", "chime", "boxinc", "lattice", "waymo", "block",
        "twitch", "okta", "zscaler", "fastly", "cockroachlabs", "fivetran", "mixpanel",
        "launchdarkly", "coursera", "udacity", "roblox", "pagerduty", "bitwarden", "netlify",
        "togetherai", "epicgames", "riotgames", "gemini", "ripple", "fireblocks",
        "circleci", "nuro")),
    ("Greenhouse boards (US East)", "greenhouse", "ABŞ şərq sahili", (
        "datadog", "mongodb", "gitlab", "toast", "zocdoc", "justworks", "duolingo", "squarespace",
        "klaviyo", "peloton", "oscar", "betterment", "attentive", "yext", "grafanalabs",
        "pendo", "classpass", "udemy", "khanacademy", "fanduel", "thenewyorktimes", "hp",
        "constantcontact", "braze", "gongio", "salesloft", "apolloio", "zoominfo", "sproutsocial")),
    ("Greenhouse boards (Canada)", "greenhouse", "Kanada", (
        "d2l", "faire", "geotab", "hootsuite", "ritual", "shakepay", "lucidsoftware", "leagueinc")),
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
    # Dry-run 2026-10-11 of ~60 more boards (Greenhouse/Lever/Workable): only these four gave
    # accepted ads; sysdig, pigment, scaleway, honeycomb, cribl, bitgo, etc. were all office or
    # country-locked and were not added.
    ("Greenhouse boards (Remote-first & global)", "greenhouse", "Remote-first və qlobal işə götürən şirkətlər", (
        "mozilla", "wikimedia", "consensys", "tomorrow")),
    # 2026-10-11 expansion: boards from the public ATS lists (kalil0321/ats-scrapers) kept by
    # scripts/sweep_ats_boards.py (tech titles + Remote/Anywhere/EMEA/relocation/visa signal) and then
    # by a dry-run through finish_item on a temp DB (>= 1 accepted ad, AI off). US-restriction-risk
    # boards (axios, actblue, clearstreet, allegiantair, cgsfederal, agile-defense, kepler...) left out.
    # Each group has <= 40 boards; at ATS_MAX_BOARDS=20 a full rotation takes <= 2 passes (6 h).
    ("Greenhouse boards (Remote & relocation 1)", "greenhouse", "Remote və ya relocation siqnallı lövhələr (süpürmə 2026-10-11)", (
        "agency", "monzoreferrals", "etchedai", "distantjob", "yipitdata", "think-cell",
        "eqvilentjobs", "platacard", "doitintl", "muonspace", "vannevarlabs", "glydways",
        "sparkadvisors", "stackblitz", "axle", "atomicindustriesinc", "solutions",
        "fueledcareers", "garnerhealth", "opensesame", "dyopath", "abinbev", "federato",
        "leolabsinc", "extend", "quisitivejobs", "knightdivisiontactical", "menaconsultant",
        "sourcegraph91", "novacredit", "yipitdatajobs", "teravision", "alpaca", "apiphani",
        "ardentmc", "clarityinnovates")),
    ("Greenhouse boards (Remote & relocation 2)", "greenhouse", "Remote və ya relocation siqnallı lövhələr (süpürmə 2026-10-11)", (
        "edb", "freenome", "devtechnology", "dwelly", "automatticcareers", "beyondfinance",
        "crossriverbank", "digible", "flexport", "ezcaterinc", "formhealth", "gruns",
        "orderly", "scotch", "roo", "recidiviz", "neweratech", "k2spacecorporation",
        "sigmacomputing", "censys", "amplemarket", "bpcs", "counterpart", "carrotfertility",
        "applytoaktos", "apexcompanies", "altamirafreelance", "thedutchie", "cakeai",
        "chronograph", "daymarkhealth", "cortex", "alxafrica", "b12", "catchcreationllc",
        "rapidfortinc")),
    ("Greenhouse boards (Remote & relocation 3)", "greenhouse", "Remote və ya relocation siqnallı lövhələr (süpürmə 2026-10-11)", (
        "future", "burnt", "figure", "focused", "paynearmeinc", "honehealth",
        "hopscotchprimarycare", "lucenia", "gametimeunited", "phaidra", "goodwaygroup",
        "hopskipdrive", "horacemannservicecorporation", "inkind", "calahealth", "oportun",
        "iovancebiotherapeutics", "medicalinformaticsengineering", "neuehealth",
        "oneimaging", "postscript", "qohash", "renewedvision", "sifthealthcare", "spektrum",
        "mrbeastyoutube", "phizenix", "optiverprivate", "tensorops", "webchartnow",
        "customerio", "boulevard", "buzzsolutions", "astspacemobile", "csciconsulting",
        "altentechnologyusa")),
    ("Greenhouse boards (Remote & relocation 4)", "greenhouse", "Remote və ya relocation siqnallı lövhələr (süpürmə 2026-10-11)", (
        "assemblyai", "brave", "soldejaneiro", "coterieinsurance", "dante", "eclipse",
        "charliehealth", "codeblack", "dvtrading", "emoneyadvisor", "alfredbeneschco",
        "12twenty", "assetwatch", "crowellmoring", "elend", "guidepointsecurity",
        "growetalents", "humansignal", "eqtcorporation", "extrahopnetworks", "growe",
        "devfuturetalent", "galaxydigitalservices", "generalassembly", "incidentiq",
        "audiaelastomers", "avochato", "thewilshiregroup", "trivelta", "insightrx",
        "swayable", "blip-global", "vertalents", "pluspower", "hanwharenewables",
        "hummingbirdregtech")),
    ("Greenhouse boards (Remote & relocation 5)", "greenhouse", "Remote və ya relocation siqnallı lövhələr (süpürmə 2026-10-11)", (
        "hungryroot", "imagineworldwide", "koboldmetals", "talkdesk2", "olipop",
        "systemstechnologyresearch", "ladder33", "onesixsolutions27", "opploans",
        "parsleyhealth", "radiclehealth", "relationalai", "samsungnext", "shapercapital",
        "sixfold", "saasgroup", "koalafi", "manifest", "mcghealth", "kettle", "mntn",
        "onepath", "recast", "selinicapital", "siliconranch", "turbineone", "zambold",
        "tekmetric", "telnyx54", "warp", "wooga", "voyagertechnologiesinc", "wayvia",
        "wonderschool", "zenbusiness")),
    ("Greenhouse boards (Remote & relocation 6)", "greenhouse", "Remote və ya relocation siqnallı lövhələr (süpürmə 2026-10-11, 2-ci dalğa)", (
        "soraunion", "sandtechholdingslimited", "linkedinlimitedpostings", "vetto",
        "testlio", "twindo", "rootstocklabsltd", "offshorelaunch")),
    ("Greenhouse boards (Remote & relocation 7)", "greenhouse", "Remote siqnallı lövhələr (dry-run, 3-cü dalğa)", (
        "kayzen", "openzeppelin", "recall", "miris",
        "strike", "flex", "archer56")),
    # ---- Lever (api.lever.co)
    ("Lever boards (Europe)", "lever", "Avropa", (
        "spotify", "qonto", "swile", "aircall", "zopa", "farfetch", "malt", "blablacar",
        "contentsquare", "pipedrive", "lodgify", "jobandtalent", "dreamgames", "peakgames",
        "trendyol")),
    ("Lever boards (Americas)", "lever", "Şimali və Latın Amerikası", (
        "palantir", "toptal", "anchorage", "olo", "fullscript", "outreach", "jumpcloud", "ro",
        "zoox", "wattpad", "relay", "dlocal", "kavak")),
    ("Lever boards (India)", "lever", "Hindistan", (
        "meesho", "paytm", "zeta", "mindtickle", "fampay", "cred")),
    ("Lever boards (Asia-Pacific)", "lever", "Şərqi və Cənub-Şərqi Asiya, Avstraliya", (
        "woven-by-toyota", "crypto", "lalamove", "nium", "ninjavan", "binance", "deputy",
        "immutable")),
    ("Lever boards (Remote & relocation 1)", "lever", "Remote və ya relocation siqnallı lövhələr (süpürmə 2026-10-11)", (
        "metabase", "quantco-", "Anovium", "cscgeneration-2", "amanotes",
        "InfrastructureandCapitalProjects", "zencore", "synapticure", "vrchat", "nibiru",
        "Onehouse", "floqast", "cyara", "significanceinc", "voltus", "accesssoftek",
        "distru", "postera", "Termius")),
    # ---- Teamtailor ({company}.teamtailor.com/jobs.rss)
    ("Teamtailor boards (Nordics)", "teamtailor", "Skandinaviya", (
        "tibber", "polestar", "anyfin", "instabee", "templafy", "detectify", "doktor", "bannerflow",
        "brite", "lunar", "storytel", "naturalcycles", "fishbrain", "quinyx", "hedvig", "bambuser")),
    ("Teamtailor boards (Rest of Europe)", "teamtailor", "Baltikyanı və digər Avropa", (
        "starship", "carvertical", "seedtag")),
    # ---- Breezy HR ({company}.breezy.hr/json)
    ("Breezy boards (Remote)", "breezy", "Remote siqnallı Breezy lövhələri", (
        "ismira", "social-discovery-ventures", "1001", "fuelerate", "superdispatch",
        "20four7va", "yallaplay", "a-hiringgroup", "betclic-group", "blenderbox", "census",
        "entermotion", "gen-tech", "helpware-inc", "jibble-group", "ltg", "manypixels",
        "onedome", "ontrac-solutions-llc", "pixery", "recruiting", "startupblink")),
    # ---- Pinpoint ({company}.pinpointhq.com/postings.json)
    ("Pinpoint boards (Remote)", "pinpoint", "Remote və ya relocation siqnallı Pinpoint lövhələri", (
        "rowdentech", "tabby", "trilongroup", "wealthwizards")),
    # ---- Workable (apply.workable.com widget): slug sweep + dry-run 2026-10-13
    ("Workable boards (Remote & relocation 1)", "workable", "Relocation və ya remote siqnallı Workable lövhələri", (
        "deeplight", "arondite", "rebellion", "newcode", "hack-the-box-ltd",
        "nology", "nu-quantum", "payabl", "smartnews", "aurora-3",
        "comeon-group", "covergo", "rapyuta-robotics", "libertexgroup", "pinely",
        "goreel", "3-oaks-gaming", "fpmarkets", "suade", "umpisa-inc",
        "cvector", "eqltech", "twgai", "continuum-resource-network", "dyania-health",
        "epay", "moreton-capital-partners", "speakitjobs", "patrique-mercier-recruitment-fr", "mercier-consultancy")),
    # ---- Recruitee ({company}.recruitee.com/api/offers/): slug sweep + dry-run 2026-10-13
    ("Recruitee boards (Remote & relocation 1)", "recruitee", "Relocation və ya remote siqnallı Recruitee lövhələri", (
        "ascendingai", "topicsoftwaredevelopment", "kaizo", "riverflex", "shypple",
        "erstedigital", "surfly", "taroko")),
    # ---- Ashby (jobs.ashbyhq.com): slug sweep + dry-run 2026-10-13
    ("Ashby boards (Remote & relocation 1)", "ashby", "Qlobal remote, EMEA və ya relocation siqnallı Ashby lövhələri", (
        "supabase", "constructor", "trust-wallet", "fundamental", "railway",
        "n8n", "whippy", "ava-labs", "squads", "far.ai",
        "qed-ai", "hyperhug", "dualentry", "percona", "wetravel",
        "wundergraph", "poolside", "oplabs", "anagram", "neara")),
]
