# Day 1: GTFS data feasibility audit

**Audit date:** 2026-11-12  
**Accessible feed snapshot:** [UngalSoththu/ChennaiGTFS](https://github.com/ungalsoththu/ChennaiGTFS), repository snapshot `af0742dba777f9657ed6fda2046d6c2a721d630b`  
**Official portal referenced by the feed maintainer:** [CUMTA Transit Data portal](https://test.cumta.org)

## Finding: usable data exists, but do not treat all feeds as current or as direct CUMTA exports

The accessible mirror provides separate MTC bus, CMRL Metro, and Southern Railway GTFS archives, as well as a unified feed. It identifies CMRL and suburban rail as sourced from CUMTA and MTC as sourced from the MTC app timetable scrape. Therefore, the MTC archive is useful for the project, but it does **not** establish that the CUMTA MTC export has usable times.

The mirror's README reports the following feed sizes. These counts are reported by the source repository and have not yet been independently recomputed in this project; run `python scripts/audit_gtfs.py` to inspect the downloaded archives and produce local counts.

| Feed | Stops | Routes | Trips | Stop-time rows | Core files |
|---|---:|---:|---:|---:|---|
| MTC buses (mirror/app timetable scrape) | 5,580 | 4,611 | 47,047 | 1,360,443 | `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`, `calendar.txt` |
| CMRL Metro (CUMTA-derived) | 254 | 28 | 625 | 12,503 | Same five core files |
| Southern Railway suburban (CUMTA-derived) | 708 | 763 | 763 | 16,135 | Same five core files |
| Unified | 6,542 | 5,402 | 48,435 | 1,389,081 (source says 1.39M) | Same five core files |

## Data quality and fare findings

- **MTC stop times:** The mirror describes its app-scraped timetable as real. The source warns that CUMTA's separate `static_mtc_gtfs_data.zip` has placeholder `00:00:15` departures for 4,721 trips. Do not silently substitute that CUMTA file for the mirror's MTC feed. Audit the actual chosen archive's time values before routing.
- **Metro stop times:** The source describes real departure times. Its CUMTA-derived calendar ends **2021-12-31**, so the schedule is stale and should be treated as structural/historical until a current calendar is verified.
- **Suburban rail:** The feed is present, but the source says each of its 763 services is represented as one daily trip pattern rather than per-train timetables. Confirm whether that granularity is sufficient for departure-time routing.
- **Stop sequence:** The source lists populated stop-time tables but does not publish a sequence-integrity result. The audit script checks missing, invalid, duplicate, and non-increasing `stop_sequence` values per trip; it also reports gaps without incorrectly treating gaps as invalid (GTFS requires increasing order, not necessarily consecutive integers).
- **Fares:** CMRL `fare_attributes.txt` and `fare_rules.txt` are present in the mirror and describe zone fares, but the source says the chart is dated **22 February 2021**. The MTC feed has no fare files; its source explicitly identifies MTC fare data as missing. Build bus fares from a separately verified published fare table, and label any estimate honestly.
- **Direct CUMTA downloads:** The CUMTA portal is identified as `https://test.cumta.org`, but the repository notes it uses an encrypted API. This audit uses the public mirror's downloadable archives for reproducibility; it does not claim to have fetched a direct CUMTA MTC archive.

## Required next action

Run the audit script and retain its JSON/console report with the exact archive URLs and date. Before using a feed for itinerary timing, verify that its service calendar is active for the requested date and inspect placeholder/invalid times. If CUMTA's MTC export is required, retrieve it separately from the portal and audit it independently; the app-scraped MTC mirror is not evidence that the CUMTA export's timings are valid.

## Sources

- [ChennaiGTFS source README](https://github.com/ungalsoththu/ChennaiGTFS/blob/af0742dba777f9657ed6fda2046d6c2a721d630b/README.md)
- [MTC feed archive](https://github.com/ungalsoththu/ChennaiGTFS/blob/af0742dba777f9657ed6fda2046d6c2a721d630b/data/mtc-gtfs.zip)
- [CMRL feed archive](https://github.com/ungalsoththu/ChennaiGTFS/blob/af0742dba777f9657ed6fda2046d6c2a721d630b/data/cmrl-gtfs.zip)
- [Suburban rail feed archive](https://github.com/ungalsoththu/ChennaiGTFS/blob/af0742dba777f9657ed6fda2046d6c2a721d630b/data/srr-gtfs.zip)
- [CUMTA Transit Data portal](https://test.cumta.org)
