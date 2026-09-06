Raw source tables backing open-reading-layer provenance work
(plans/2026-09-06-open-reading-layer.md, Phase 1).

- `van-buskirk-sermon-list-2016.pdf` — Gregory P. Van Buskirk, "John Wesley's
  Sermons" (compiled June 2016), fetched from
  https://wesleyworks.ecdsdev.org/editorial-docs/201705jw-sermon-lists.pdf
  (the Wesley Works Digitization Project's own editorial-docs page). Collates
  Appendices E, F, G of *The Bicentennial Edition of the Works of John
  Wesley*, ed. Albert C. Outler (Abingdon, 1984ff.), 4:540-573, plus Sugden's
  taxonomy for Sermons 1-53.
- `van-buskirk-sermon-list-2016.csv` — that PDF transcribed to CSV, all 151
  Bicentennial-numbered sermons plus the two split/unpublished sub-entries
  (138a, 138b-c). `jackson_running` is the informal 1-141 numbering used by
  Jackson's own 1872 edition and by wesley.nnu.edu / ResourceUMC (and thus by
  this repo's `jw-sermon-NNN` source_ids) — NOT the same as `bicentennial`
  except where they coincide (sermons 1-108).
- `van-buskirk-jackson-non-wesley-sermons.csv` — the 4 sermons Jackson bundled
  into his own numbering (129, 137, 138, 141) that the Bicentennial editors
  identify as written by someone other than John Wesley.
