"""
Known corporate landowner → real owner lookup table.

Sources: MT Secretary of State filings, public reporting, news articles.
This is used by the parcel processing pipeline to enrich corporate entities
with the actual person/family behind the LLC/LP/Inc.

To add new entries: add to KNOWN_OWNERS dict below.
Key = uppercase owner name from cadastral data.
Value = dict with real_owner (person), notes (context).
"""

KNOWN_OWNERS = {
    # === Top 30 by acreage (researched March 2026) ===

    "FARMLAND RESERVE INC": {
        "real_owner": "LDS Church (investment arm)",
        "notes": "Tax-exempt agricultural investment arm of Church of Jesus Christ of Latter-day Saints",
    },
    "GREEN DIAMOND RESOURCE COMPANY": {
        "real_owner": "Reed/Simpson family",
        "notes": "6th-gen timber family; formerly Simpson Logging Co (1890); HQ Shelton WA",
    },
    "WILKS RANCH MONTANA LTD": {
        "real_owner": "Dan & Farris Wilks",
        "notes": "TX fracking billionaires (Frac Tech); ~341K acres across 7 MT counties",
    },
    "71 RANCH LP": {
        "real_owner": "Errol & Sharrie Galt",
        "notes": "Multi-generational MT ranchers; ~262K family acres total",
    },
    "SUNLIGHT RANCH COMPANY": {
        "real_owner": "Holding family (Earl Holding heirs)",
        "notes": "Earl Holding (d. 2013) owned Sinclair Oil & Sun Valley; ~400K acres MT/WY",
    },
    "COFFEE NEFSY LIMITED PARTNERSHIP": {
        "real_owner": "Coffee/Nefsy family (William E. Coffee)",
        "notes": "Agent: William E Coffee, Billings MT; founded Stockman Bank family",
    },
    "STIMSON LUMBER CO": {
        "real_owner": "Stimson/Reed/Miller family",
        "notes": "Private since 1850s; one of largest private forest companies in US",
    },
    "BROKEN O LAND & LIVESTOCK LLC": {
        "real_owner": "Stan Kroenke",
        "notes": "Sports billionaire (LA Rams, Arsenal FC); ~225K total MT acres",
    },
    "SPP MONTANA LLC": {
        "real_owner": "Benjy Griffith (Southern Pine Plantations)",
        "notes": "Founded SPP 1984; bought 630K Weyerhaeuser acres in 2019",
    },
    "BEAVERHEAD RANCH PROPERTY LLC": {
        "real_owner": "Rupert Murdoch",
        "notes": "Purchased from Koch/Matador in 2021 for ~$200M",
    },
    "HEAL HOLDINGS LLC": {
        "real_owner": "Charlotte de Meevius",
        "notes": "Belgian philanthropist; bought Diamond Cross Ranch (Birney) for $64.8M in 2017",
    },
    "GALT RANCH LP": {
        "real_owner": "Bill Galt & family",
        "notes": "Same dynasty as 71 Ranch; near White Sulphur Springs",
    },
    "GREAT NORTHERN PROPERTIES LP": {
        "real_owner": "Corbin J. Robertson Jr.",
        "notes": "Houston; acquired BN Railroad coal assets 1992; largest private coal reserves in US",
    },
    "TURNER MONTANA PROPERTIES LLC": {
        "real_owner": "Ted Turner",
        "notes": "2nd largest individual landholder in N. America; Flying D, Snowcrest, Bar None ranches",
    },
    "TURNER ENTERPRISES INC": {
        "real_owner": "Ted Turner",
        "notes": "Parent company of all Turner ranch operations",
    },
    "IX RANCH COMPANY LLC": {
        "real_owner": "Roth family (Richard, Stephen & Karen Roth)",
        "notes": "128-year-old ranch near Big Sandy; originally Hamms brewery family",
    },
    "DEARBORN RANCH LLC": {
        "real_owner": "Tom Siebel",
        "notes": "Silicon Valley billionaire (Siebel Systems/C3.ai); ~70K acres near Wolf Creek",
    },
    "SCHIFFER RANCH CO": {
        "real_owner": "Schiffer family",
        "notes": "Multi-generational Rosebud MT ranchers; ~35K deeded acres",
    },
    "MY GREEN EARTH LP": {
        "real_owner": "Andy family (Audia Group)",
        "notes": "PA-based Washington Penn Plastics family; ranch in Shepherd MT",
    },
    "PV RANCH COMPANY LLC": {
        "real_owner": "Stan Kroenke",
        "notes": "Part of Kroenke's multi-ranch portfolio; manager Angela Bennett",
    },
    "CATLIN RANCH LP": {
        "real_owner": "Ben Galt",
        "notes": "4th-gen Galt family rancher; White Sulphur Springs",
    },
    "ROCK CREEK RANCH I LTD": {
        "real_owner": "Russell Gordy",
        "notes": "Houston oil & gas billionaire; paid $40M+ for 44K acres",
    },

    # === Partially identified ===
    "CHERRY CREEK SHEEP CO": {
        "real_owner": "Reukauf family (likely)",
        "notes": "Cherry Creek Ranch near Terry; homesteaded 1910",
    },
    "ROCKET LAND & LIVESTOCK LLC": {
        "real_owner": "Craig Ambler (registered agent)",
        "notes": "Denver CO; beneficial owner not publicly confirmed",
    },

    # === Other major owners from CareOfTaxpayer data ===
    "SIEBEN RANCH COMPANY": {
        "real_owner": "John Bayers",
        "notes": "CareOfTaxpayer: BAYERS JOHN",
    },
    "SIEBEN LIVESTOCK CO": {
        "real_owner": "Bayers family",
        "notes": "Related to Sieben Ranch Company",
    },
    "ANTELOPE N V": {
        "real_owner": "Unknown (Netherlands entity)",
        "notes": "NV = Naamloze vennootschap (Dutch public company)",
    },
    "GALT RANCH LP": {
        "real_owner": "Bill Galt & family",
        "notes": "Same dynasty as 71 Ranch",
    },
    "VASSAU'S FLYING X RANCH": {
        "real_owner": "Arnold Vassau",
        "notes": "CareOfTaxpayer: VASSAU ARNOLD",
    },
    "WERTHEIMER H INC & WERTHEIMER A INC": {
        "real_owner": "Wertheimer family",
        "notes": "H & A Wertheimer ranching operations",
    },

    # === Well-known Montana ranch owners ===
    "AMERICAN PRAIRIE FOUNDATION": {
        "real_owner": "American Prairie (nonprofit)",
        "notes": "Conservation nonprofit; building largest nature reserve in lower 48",
    },
    "NAVAJO TRANSITIONAL ENERGY COMPANY LLC": {
        "real_owner": "Navajo Nation (tribal enterprise)",
        "notes": "Purchased Rosebud Mine/Spring Creek Mine from Cloud Peak Energy",
    },
    "BOOTH LAND & LIVESTOCK CO": {
        "real_owner": "Mark Booth",
        "notes": "CO-based rancher",
    },
    "BOOTH LAND & LIVESTOCK": {
        "real_owner": "Mark Booth",
        "notes": "CO-based rancher (alternate entity name)",
    },
}


def lookup_real_owner(owner_name):
    """Look up the real person behind a corporate entity.
    Returns (real_owner, notes) or ('', '') if not found.
    """
    if not owner_name:
        return '', ''
    key = str(owner_name).upper().strip()
    entry = KNOWN_OWNERS.get(key)
    if entry:
        return entry['real_owner'], entry.get('notes', '')
    return '', ''
