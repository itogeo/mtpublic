# Old county roads: plan (branch `old-county-roads`, 2026-10-14)

Goal: find every road in Montana that was ever made a public road (mostly county roads set up by
petition in the 1870s to 1930s, plus roads shown on the original federal land surveys) and show
where one of them reaches public land that has no recognised access today. Pilot in Gallatin
County, starting with the Sixteen Mile Creek road we already hold (County Road 122, petitioned
and ordered opened 6 November 1897, `122_sixteenmile.pdf`).

## Why old roads matter (the law, in short; not legal advice)

- A county road created by petition is 60 ft wide (30 ft each side of centreline) unless the
  order says otherwise (MCA 7-14-2112).
- It stays a county road until it is abandoned or vacated by law, a court judgment or a
  commission order, after notice and a hearing (MCA 7-14-2615(1),(2)). A road that fell out
  of use and grew over is still a county road on paper if it was never formally abandoned.
- A commission may not abandon a road that gives legal access to public land or water unless
  substantially the same access remains (MCA 7-14-2615(3)).
- Roads can also become public by prescription (long public use), and the right-of-way then
  covers what is needed to use and maintain it (Public Lands Access Ass'n v. Madison County,
  2014, the Seyler Lane case).
- Roads that crossed unreserved federal land before 1976 may be R.S. 2477 rights-of-way.

So the hunt is: roads that exist in the record but not on today's map, or exist on the ground
but are not marked public, where they touch public land.

## What this repo already does (main)

- Statewide screen: MSDI road centrelines buffered 30 ft against public land (MSL public
  lands, DNRC trust tracts), near-miss threshold 100 ft, ranked opportunities and "unlock"
  analysis (`scripts/03_*`, `04_*`), web map in `webapp/`.
- Limitation: it only knows roads that are on today's MSDI layer, and 83% of segments have no
  owner value. Old petitioned roads that are no longer drawn are invisible to it.
- Data4 (`itogeo/data4`, `src/access/public_access.py`) has a newer statewide public-access
  status (open, corner-locked, no access, unknown) and already flags DNRC no-access tracts a
  county road comes within 30 ft of. The old-roads layer should feed both.

## Evidence ladder (strongest first)

| # | Source | What it shows | Legal weight | Access | Format |
|---|---|---|---|---|---|
| 1 | County road petitions, viewers' reports, commission orders, road books | Route, width, date ordered opened; "Road No." | The legal record of a county road | County clerk and county surveyor; mostly paper or scans; not online in Gallatin (commission minutes online only after July 2015) | Scans like `122_sixteenmile.pdf` |
| 2 | Abandonment and vacation resolutions | Which roads were legally closed | Removes a road | Commission minutes and resolutions; recent ones online | PDF |
| 3 | Certificates of survey and subdivision plats | Surveyors often draw and label "County Road No. 122, 60' R/W per petition" across or along a parcel | Strong supporting evidence, and gives modern coordinates | Gallatin recorder (Eagle Web); Data4 already builds COS links (`src/surveys/`) | Scanned PDF, OCR |
| 4 | Original federal land surveys (GLO plats and field notes, 1860s to 1910s) | Roads and trails the surveyors crossed, located by section line | Evidence a road existed early (R.S. 2477, prescription) | BLM GLO Records site, public domain | Plat images per township; field notes text |
| 5 | Historic USGS topographic maps (1890s to 1990s) | Roads, "unimproved roads", trails at each map date | Evidence of the road's existence and location over time | USGS topoView and the Historical Topographic Map Collection, public domain, georeferenced GeoTIFFs | GeoTIFF |
| 6 | Historic aerial photos (1940s to 1990s) | The physical trace on the ground | Evidence of use and location | USGS EarthExplorer single frames, public domain | Image (needs georeferencing) |
| 7 | Today's road layers | MSDI centrelines (Ownership, RoadClass), county road layers with road numbers, Forest Service roads incl. decommissioned, BLM GTLF, OpenStreetMap tracks and abandoned roads | What is recognised now | Public downloads | Vector |
| 8 | Court cases, AG opinions, PLWA cases | Known disputes and outcomes | Ground truth to test the method | Public | Text |

## Method

1. Build the "historic road" line set per township from sources 4 and 5 (and 3 where a plat
   draws a county road), each line tagged with source, date and confidence.
2. Remove what matches today's recognised public roads (source 7, within ~30 m).
3. What remains are "ghost roads": roads on old maps or old surveys that today's map does not
   call public. Keep the ones that join a public road to public land, or cross into a public
   land patch that Data4 rates no access, corner-locked or unknown.
4. Rank each lead by evidence (how many independent sources show it, how early, whether a
   plat or petition names it), by the acres of public land it would open, and by whether
   that land is otherwise locked.
5. For the top leads, look for the petition and any abandonment (sources 1 and 2). A lead with
   a petition and no abandonment is the strongest kind.
6. Publish each lead with its evidence packet: map snippets from each source, links to the
   original documents, dates, and the plain status ("petition found, no abandonment found",
   "shown on 1896 and 1951 maps, no petition found yet").

## Getting road lines out of old maps

- GLO plats are township grids, so they can be placed automatically: match the plat's
  section corners to the BLM PLSS grid (CadNSDI) with the matching-points method Data4 already
  uses for site plans (`pro/web/georef.js`, least-squares affine). Then trace roads by hand in
  the first pass (they are few per township), and test automatic line extraction later.
- Historic USGS topos are already georeferenced GeoTIFFs. Road symbols (double lines, dashed
  unimproved roads, trails) can be traced by hand for the pilot; for statewide scale, test an
  automatic extractor (colour separation plus line detection in Python; published USGS and
  academic work on road extraction from historic maps is the starting point).
- Petitions describe routes in words and section references ("commencing at ... thence to the
  Middle Fork of Sixteen Mile Creek ... to Castle"). Read them, place the named points on the
  PLSS grid and the old maps, and draw the route by hand. These are slow and few, so they are
  done only for top leads.
- COS and plats: OCR the scans and search for "county road", "road no", "petition", "R/W",
  "right of way"; place the hit by the parcel it belongs to.

## Pilot: Sixteen Mile Creek, Gallatin County

1. Transcribe Road 122's petition and viewers' report (13 pages): route, named points, width,
   dates, surveyor (C. M. Thorpe, county surveyor).
2. Pull the GLO plats for the townships the route crosses and the USGS topos covering it
   (earliest available, plus the 1950s and 1980s editions).
3. Trace the 1897 route on those maps; compare with today's MSDI roads, parcels and public
   land; mark where today's road leaves the old line and where the old line meets public land.
4. Search the Gallatin COS scans in those sections for "Road No. 122".
5. Write it up as the first evidence packet. If the method holds, run steps 2 to 4 for every
   township in Gallatin County, then the counties with the most locked public land.

## Phases and rough effort (one person with Claude)

| Phase | What | Effort |
|---|---|---|
| 0 | This branch, plan, source register (robots and terms for each host) | done today / 1 day |
| 1 | Pilot on Road 122 (transcription, GLO, topos, trace, COS search, packet) | 3 to 5 days |
| 2 | Gallatin County: GLO plats and topos for every township with locked public land; hand tracing; ghost-road candidates; ranking | 2 to 3 weeks |
| 3 | Automatic line extraction from historic topos, tested against the Gallatin hand tracing | 2 to 4 weeks |
| 4 | Statewide screen with automatic extraction; leads ranked; petitions looked up only for the top leads | ongoing |
| 5 | Map layer in this repo's web map and in Data4's public access view; evidence packets | 1 to 2 weeks |

## Rules

- Public records only, from the agency's own public site or service. robots.txt checked
  before any request (copy Data4's `src/ops/house_rules.py`), one request at a time, cached.
- No records requests, emails or letters for now (standing decision, 2026-10-07). Petitions
  beyond the one we hold wait until Ian says go; list which ones we would ask for.
- Leads are leads, not legal conclusions. Every published lead says what was found and what
  was not found, and that a road's status is decided by the county commission or a court.
- No private individuals' names on the map or in packets (petitioners in 1897 are historic
  record and can be cited from the document, but current landowners are not named). Nothing
  that encourages trespass; corner crossing is trespass in Montana.
- This repo is public. Decide before publishing leads (see questions).

## Questions for Ian

1. Where did `122_sixteenmile.pdf` come from (county surveyor, road department, a PLWA
   contact)? If the county has a scanned road-petition set, that is the fastest path.
2. Publish leads in this public repo and site, keep them private in Data4 Pro, or share
   privately with PLWA or FWP first?
3. Pilot area: Sixteen Mile Creek, or another place you already suspect?
4. Should this branch also move the web map onto Data4's newer public-access status, or keep
   this repo separate?
