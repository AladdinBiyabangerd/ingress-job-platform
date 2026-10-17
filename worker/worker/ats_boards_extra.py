"""More employer boards (2026-10-17 wave), kept apart from ats_boards.py.

Same shape as ats_boards.GROUPS: (source name, ATS, Azerbaijani region label,
board slugs). Every slug was checked on 2026-10-17 with
scripts/verify_ats_slugs.py: robots.txt allows the board URL, the board
answers, it lists tech roles and at least one of its ads passes the
acceptance rules (finish_item, AI off). Use all_groups() for the full list.
"""

from worker.ats_boards import GROUPS

MORE_GROUPS: list[tuple[str, str, str, tuple[str, ...]]] = [
    # ---- Ashby (jobs.ashbyhq.com hosted boards; api.ashbyhq.com robots.txt answers 401)
    # From the 2026-10-13 Ashby sweep (passes that were never reviewed) plus first checks
    # of well-known boards; re-verified 2026-10-17. Left out: clera (recruiting
    # marketplace), circle / monarchmoney / witnessai / ascertain (only one weak ad), and
    # test, VC, studio, agency or onsite-only boards.
    ("Ashby boards (Crypto & Web3)", "ashby", "Qlobal remote: kripto, Web3 və AI infrastrukturu", (
        "0x", "doublezero", "hyperbolic", "lightning", "magiceden", "polymarket", "provable",
        "rain", "syndica", "tempo-xyz")),
    ("Ashby boards (AI, security & dev tools)", "ashby", "Remote: AI, təhlükəsizlik və developer alətləri şirkətləri", (
        "artemis", "bedrockocean", "clerk", "conduit", "decagon", "eloquentai",
        "empirical-security", "endgame", "ent-security", "everops", "fathom.video", "flox",
        "havocai", "leantechniques", "moxfive", "neuroscale", "northflank.com", "oscilar",
        "people-data-labs", "prefect", "preql", "protege", "reliable-robotics", "replicant",
        "roboflow", "runway-ml", "socket", "sola", "southgeeks", "tavus", "valon",
        "withwisdom", "wynd-labs")),
    ("Ashby boards (Americas remote)", "ashby", "Əsasən Amerika mərkəzli remote məhsul şirkətləri (SaaS, fintech, sağlamlıq texnologiyası)", (
        "a-place-for-mom", "acorns", "assured", "atticus", "classdojo", "clickup", "givebutter",
        "gridunity", "gridverify", "headway", "imprint", "jobber", "jobs-valence", "kin", "kit",
        "mdcalc", "mudflap", "nava-benefits", "ncontracts", "nextpatient", "novellia", "nylas",
        "overflow", "payabli", "playlab", "prompt", "rarecandy", "realmalliance",
        "schoolhouse-world", "stickermule", "tango", "truemed", "vetcove", "virtahealth",
        "vitalize", "yendo")),
    # ---- Lever (api.lever.co): leftovers of the 2026-10-11 signal sweep that had never been
    # dry-run, plus offchainlabs; verified 2026-10-17 (octoenergy left out: GB-only remote).
    ("Lever boards (Remote & relocation 4)", "lever", "Remote siqnallı Lever lövhələri (yoxlama 2026-10-17)", (
        "offchainlabs", "includedhealth", "vedatechlabs", "happy-sleep", "truetandem",
        "truezerotech")),
]


def all_groups() -> list[tuple[str, str, str, tuple[str, ...]]]:
    """ats_boards.GROUPS followed by MORE_GROUPS (source names are unique)."""
    return list(GROUPS) + list(MORE_GROUPS)
