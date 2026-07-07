#!/usr/bin/env python3.11
"""Author metadata/sentinel-quotes.jsonl — the Wesley corpus regression net.

Phase 3c of plans/2026-07-07-swi-v2-ocr-cleanup-verification.md.
~50 famous Wesley passages with canonical wording + expected source. Built and
verified against chunked/cleaned_passages.jsonl BEFORE any OCR cleaning, so the
first run's failures are the baseline the cleanup phases must close.

Each sentinel:
  id            slug
  author        john-wesley | charles-wesley
  work          human title
  reference     canonical citation (edition-independent)
  source_id     expected serving source_id (best-known location)
  alt_source_ids  other legitimate loci (optional)
  anchor        SHORT, distinctive, OCR-robust locate key (lowercased match)
  canonical     verbatim expected wording from the critical text (tolerance-compared)
  expect        "present" (default) | "absent"  -- absent = anti-contamination tripwire
  catches       what a failure reveals
  notes         authenticity / known-garble / missing-content flag (optional)

Run: python3.11 scripts/build_sentinel_quotes.py   (writes file + prints baseline)
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVING = os.path.join(ROOT, "chunked", "cleaned_passages.jsonl")
OUT = os.path.join(ROOT, "metadata", "sentinel-quotes.jsonl")

rows = [json.loads(l) for l in open(SERVING, encoding="utf-8")]


def present_in(source_id, needle):
    n = needle.lower()
    return [r for r in rows if r["source_id"] == source_id and n in r["text"].lower()]


def anywhere(needle):
    n = needle.lower()
    return [r for r in rows if n in r["text"].lower()]


# --- auto-resolve two genuine-Wesley Notes anchors (anti-Barnes positive net) ---
def first_present(source_id, candidates):
    for c in candidates:
        if present_in(source_id, c):
            return c
    return None


nt_anchor = first_present("jw-notes-nt", [
    "the spirit himself", "jesus wept", "out of sympathy", "verily, verily",
    "the word was god", "in the beginning was the word",
])
ot_anchor = first_present("jw-notes-on-old-testament", [
    "in the beginning god created", "let there be light", "the lord is my shepherd",
    "and god saw the light", "god created the heaven",
])

S = []  # sentinels


def add(**kw):
    kw.setdefault("expect", "present")
    S.append(kw)


# ========================= JOHN WESLEY — JOURNAL =========================
add(id="aldersgate-strangely-warmed", author="john-wesley",
    work="Journal", reference="Journal, 24 May 1738",
    source_id="jw-journal-vol1-3",
    anchor="i felt my heart strangely warmed",
    canonical="About a quarter before nine, while he was describing the change which God works in the heart through faith in Christ, I felt my heart strangely warmed. I felt I did trust in Christ, Christ alone for salvation; and an assurance was given me that he had taken away my sins, even mine, and saved me from the law of sin and death.",
    catches="OCR damage in the corpus's single most iconic passage (baseline: 'trust 'n Christ').")
add(id="world-my-parish", author="john-wesley",
    work="Journal", reference="Journal, 11 June 1739 (also Letter to James Hervey, 20 Mar 1739)",
    source_id="jw-journal-vol1-3",
    alt_source_ids=["jw-letter-1739-04-to-james-hervey"],
    anchor="i look upon all the world as my parish",
    canonical="I look upon all the world as my parish; thus far I mean, that, in whatever part of it I am, I judge it meet, right, and my bounden duty, to declare unto all that are willing to hear, the glad tidings of salvation.",
    catches="Presence and wording of Wesley's signature line across two independent sources.")
add(id="who-shall-convert-me", author="john-wesley",
    work="Journal", reference="Journal, 24 January 1738 (homeward from Georgia)",
    source_id="jw-journal-vol1-3",
    anchor="who shall convert me",
    canonical="I went to America to convert the Indians; but oh! who shall convert me? who, what is he that will deliver me from this evil heart of unbelief?",
    catches="OCR garble in the Georgia-return passage (baseline: 'T went to America', 'but.O!').")

# ============================== SERMONS ==============================
add(id="salvation-by-faith-grace", author="john-wesley",
    work="Sermon 1: Salvation by Faith", reference="Sermon 1 (1738)",
    source_id="jw-sermon-001",
    anchor="of his mere grace, bounty, or favour",
    canonical="All the blessings which God hath bestowed upon man are of his mere grace, bounty, or favour: his free, undeserved favour; favour altogether undeserved; man having no claim to the least of his mercies.",
    catches="Opening thesis of the first Standard Sermon.")
add(id="almost-christian", author="john-wesley",
    work="Sermon 2: The Almost Christian", reference="Sermon 2 (1741)",
    source_id="jw-sermon-002",
    anchor="does nothing which the gospel forbids",
    canonical="The almost Christian does nothing which the gospel forbids. He taketh not the name of God in vain; he blesseth, and curseth not.",
    catches="Wording of the almost/altogether distinction.")
add(id="witness-of-the-spirit", author="john-wesley",
    work="Sermon 10: The Witness of the Spirit", reference="Sermon 10 (text Rom. 8:16)",
    source_id="jw-sermon-010",
    anchor="beareth witness with our spirit",
    canonical="The Spirit itself beareth witness with our spirit, that we are the children of God.",
    catches="A doctrinal-standard sermon's governing text.")
add(id="means-of-grace-definition", author="john-wesley",
    work="Sermon 16: The Means of Grace", reference="Sermon 16 (1746)",
    source_id="jw-means-of-grace",
    anchor="outward signs, words, or actions",
    canonical="By 'means of grace' I understand outward signs, words, or actions, ordained of God, and appointed for this end, to be the ordinary channels whereby he might convey to men preventing, justifying, or sanctifying grace.",
    catches="Wesley's definition of the means of grace.")
add(id="catholic-spirit-give-me-thine-hand", author="john-wesley",
    work="Sermon 39: Catholic Spirit", reference="Sermon 39 (1750)",
    source_id="jw-catholic-spirit",
    anchor="give me thine hand",
    canonical="If thine heart is as my heart, if thou lovest God and all mankind, I ask no more: 'give me thine hand.'",
    catches="The catholic-spirit refrain (v1 needed special handling for this text).")
add(id="use-of-money-gain", author="john-wesley",
    work="Sermon 50: The Use of Money", reference="Sermon 50",
    source_id="jw-sermon-050",
    anchor="gain all you can",
    canonical="Gain all you can, without hurting either yourself or your neighbour, in soul or body.",
    catches="First head of the money maxims.")
add(id="use-of-money-give", author="john-wesley",
    work="Sermon 50: The Use of Money", reference="Sermon 50 (third head)",
    source_id="jw-sermon-050",
    anchor="give all you can",
    canonical="Then 'give all you can.'",
    catches="Third and climactic money maxim (gain/save/give are the sermon's three heads, filed as separate sentinels).",
    notes="The triad is distributed across the sermon; use-of-money-gain + use-of-money-give bracket it.")
add(id="christian-perfection-babe", author="john-wesley",
    work="Christian Perfection", reference="A Plain Account of Christian Perfection (1766)",
    source_id="jw-treatise-plain-account-of-christian-perfection",
    anchor="so far perfect as not to commit sin",
    canonical="But even babes in Christ are so far perfect as not to commit sin. This St. John affirms expressly.",
    catches="The core claim of the Perfection treatise.")
add(id="free-grace-free-in-all-for-all", author="john-wesley",
    work="Sermon 128: Free Grace", reference="Sermon 128 (1739)",
    source_id="jw-free-grace",
    anchor="free in all, and free for all",
    canonical="The grace or love of God, whence cometh our salvation, is FREE IN ALL, and FREE FOR ALL.",
    catches="Thesis of Wesley's frontal attack on predestination (the acid-test text for SWI too).")
add(id="free-grace-horrible-decree", author="john-wesley",
    work="Sermon 128: Free Grace", reference="Sermon 128",
    source_id="jw-free-grace",
    anchor="horrible decree",
    canonical="This is the blasphemy clearly contained in the horrible decree of predestination! And here I fix my foot. On this I join issue with every assertor of it.",
    catches="Wesley REFUTING the 'horrible decree' — advocacy-vs-refutation ground truth.")
add(id="not-almost-but-altogether", author="john-wesley",
    work="Sermon (recurrent formula)", reference="e.g. Sermon 81, On the Death of Mr. Whitefield",
    source_id="jw-sermon-081",
    anchor="not almost, but altogether",
    canonical="not almost, but altogether Christians",
    catches="Recurrent Wesleyan formula; presence across sermons.")

# ==================== TREATISES / DOCTRINAL STANDARDS ====================
add(id="general-rules-do-no-harm", author="john-wesley",
    work="The Nature, Design, and General Rules of the United Societies",
    reference="General Rules (1743)",
    source_id="jw-general-rules",
    alt_source_ids=["jw-treatise-rules-of-the-united-societies"],
    anchor="doing no harm, by avoiding evil",
    canonical="It is therefore expected of all who continue therein that they should continue to evidence their desire of salvation, First: By doing no harm, by avoiding evil of every kind.",
    catches="First of the three General Rules (a doctrinal standard).")
add(id="general-rules-attend-ordinances", author="john-wesley",
    work="The General Rules of the United Societies", reference="General Rules (1743)",
    source_id="jw-general-rules",
    alt_source_ids=["jw-treatise-rules-of-the-united-societies"],
    anchor="attending upon all the ordinances",
    canonical="Thirdly: By attending upon all the ordinances of God.",
    catches="Third General Rule; anchors the ordinances-of-grace triad.")
add(id="general-rules-flee-wrath", author="john-wesley",
    work="The General Rules of the United Societies", reference="General Rules (1743)",
    source_id="jw-general-rules",
    anchor="desire to flee from the wrath to come",
    canonical="There is only one condition previously required of those who desire admission into these societies: a desire to flee from the wrath to come, to be saved from their sins.",
    catches="The single admission condition — a doctrinal-standard phrase.")
add(id="people-called-methodists-orthodoxy", author="john-wesley",
    work="A Plain Account of the People Called Methodists",
    reference="Letter to Vincent Perronet (1748)",
    source_id="jw-treatise-plain-account-of-the-people-called-methodists",
    alt_source_ids=["jw-letter-1748-30-to-vincent-perronet"],
    anchor="orthodoxy, or right opinions",
    canonical="Orthodoxy, or right opinions, is, at best, but a very slender part of religion, if it can be allowed to be any part of it at all.",
    catches="Wesley's minimizing-of-opinion maxim; appears in the Perronet letter and the treatise.")
add(id="perronet-one-condition", author="john-wesley",
    work="A Plain Account of the People Called Methodists",
    reference="Letter to Vincent Perronet (1748), §8",
    source_id="jw-letter-1748-30-to-vincent-perronet",
    alt_source_ids=["jw-letters-1748"],
    anchor="one condition previously required",
    canonical="There is only one condition previously required in those who desire admission into these societies — a desire to flee from the wrath to come, to be saved from their sins.",
    catches="Bulk-ingested letter corpus: presence + wording in the individually-filed letters.")
add(id="character-of-a-methodist", author="john-wesley",
    work="The Character of a Methodist", reference="The Character of a Methodist (1742)",
    source_id="jw-treatise-character-of-a-methodist",
    alt_source_ids=["jw-character"],
    anchor="a methodist is one who has",
    canonical="A Methodist is one who has 'the love of God shed abroad in his heart by the Holy Ghost given unto him'; one who loves the Lord his God with all his heart, and with all his soul, and with all his mind, and with all his strength.",
    catches="The defining sentence of the Methodist self-portrait.")
add(id="plain-truth-for-plain-people", author="john-wesley",
    work="Preface to Sermons on Several Occasions",
    reference="Preface to the Sermons (1746)",
    source_id="jw-character",
    anchor="plain truth for plain people",
    canonical="plain truth for plain people",
    catches="Wesley's plain-style manifesto (quoted within the corpus).",
    notes="The line originates in the Sermons preface; here it is found embedded in jw-character.")
add(id="farther-appeal-by-salvation-i-mean", author="john-wesley",
    work="A Farther Appeal to Men of Reason and Religion",
    reference="A Farther Appeal, Pt. I",
    source_id="jw-treatise-farther-appeal-part-1",
    anchor="by salvation i mean, not barely",
    canonical="By salvation I mean, not barely, according to the vulgar notion, deliverance from hell, or going to heaven; but a present deliverance from sin, a restoration of the soul to its primitive health.",
    catches="Wesley's definition of salvation as present deliverance.")
add(id="predestination-calmly-considered", author="john-wesley",
    work="Predestination Calmly Considered",
    reference="Predestination Calmly Considered (1752)",
    source_id="jw-treatise-predestination-calmly-considered",
    anchor="unconditional election",
    canonical="the decree of unconditional election; even in the same uprightness wherein you reject and abhor that of unconditional reprobation.",
    catches="Presence + wording of the major anti-Calvinist treatise.")

# ============================== NOTES (anti-Barnes) ==============================
if nt_anchor:
    add(id="notes-nt-genuine-wesley", author="john-wesley",
        work="Explanatory Notes upon the New Testament",
        reference="Notes on the NT (1755)",
        source_id="jw-notes-nt",
        anchor=nt_anchor,
        canonical=present_in("jw-notes-nt", nt_anchor)[0]["text"].strip()[:220],
        catches="The genuine 1755 Wesley NT Notes text (guards against the 2026 Barnes re-contamination).",
        notes="Anchor auto-resolved to a phrase confirmed present in jw-notes-nt at build time.")
if ot_anchor:
    add(id="notes-ot-genuine-wesley", author="john-wesley",
        work="Explanatory Notes upon the Old Testament",
        reference="Notes on the OT",
        source_id="jw-notes-on-old-testament",
        anchor=ot_anchor,
        canonical=present_in("jw-notes-on-old-testament", ot_anchor)[0]["text"].strip()[:220],
        catches="Genuine OT Notes text; presence of the largest commentary source.",
        notes="Anchor auto-resolved to a phrase confirmed present at build time.")
# anti-Barnes tripwires: 19th-c. names Wesley could not have cited. Must stay ABSENT.
for name in ["Rosenmuller", "Tholuck", "Kuinoel"]:
    add(id=f"anti-barnes-tripwire-{name.lower()}", author="john-wesley",
        work="(contamination tripwire)", reference="Albert Barnes, Notes (1830s) — must NOT appear",
        source_id="jw-notes-nt",
        anchor=name,
        canonical=name,
        expect="absent",
        catches="19th-c. scholar Wesley never cited; presence signals Barnes-style commentary crept back in.",
        notes="Negative sentinel — fails if FOUND.")

# ============================== CHARLES WESLEY — HYMNS ==============================
def hymn(id, title, source_id, anchor, canonical, catches, **extra):
    add(id=id, author="charles-wesley", work=title, reference=title,
        source_id=source_id, anchor=anchor, canonical=canonical, catches=catches, **extra)

hymn("and-can-it-be", "And Can It Be That I Should Gain", "cw-hymns-1780",
     "amazing love! how can it be",
     "Amazing love! how can it be That thou, my God, shouldst die for me!",
     "The most-sung Charles Wesley refrain.")
hymn("o-for-a-thousand-tongues", "O for a Thousand Tongues to Sing", "cw-hymns-1780",
     "a thousand tongues to sing my great",
     "O for a thousand tongues to sing My great Redeemer's praise!",
     "Hymn 1 of the 1780 Collection — the opening of Methodist hymnody.")
hymn("love-divine", "Love Divine, All Loves Excelling", "cw-love-divine",
     "love divine, all loves excelling",
     "Love divine, all loves excelling, Joy of heaven, to earth come down.",
     "Charles Wesley's crowning hymn of perfect love.")
hymn("jesus-lover-of-my-soul", "Jesus, Lover of My Soul", "cw-jesus-lover-of-my-soul",
     "jesus, lover of my soul",
     "Jesus, lover of my soul, Let me to thy bosom fly.",
     "Presence + wording of a signature hymn.")
hymn("hark-the-herald", "Hark! the Herald Angels Sing", "cw-hark-the-herald",
     "hark! the herald angels sing",
     "Hark! the herald angels sing, 'Glory to the newborn King.'",
     "Christmas hymn — first line.")
hymn("christ-the-lord-is-risen", "Christ the Lord Is Risen Today", "cw-christ-risen",
     "christ the lord is risen today",
     "Christ the Lord is risen today, Alleluia!",
     "Easter hymn — first line.")
hymn("wrestling-jacob", "Wrestling Jacob (Come, O Thou Traveller Unknown)",
     "cw-wrestling-jacob",
     "come, o thou traveller unknown",
     "Come, O thou Traveller unknown, Whom still I hold, but cannot see!",
     "Watts called this worth all his own hymns; note its stanza chunking survives.")
hymn("rejoice-the-lord-is-king", "Rejoice, the Lord Is King", "cw-rejoice-the-lord-is-king",
     "rejoice, the lord is king",
     "Rejoice, the Lord is King! Your Lord and King adore.",
     "First line + wording.")
hymn("lo-he-comes", "Lo! He Comes with Clouds Descending", "cw-lo-he-comes",
     "lo! he comes with clouds descending",
     "Lo! he comes with clouds descending, Once for favoured sinners slain.",
     "Advent hymn — first line.")
hymn("come-thou-long-expected", "Come, Thou Long-Expected Jesus",
     "cw-come-thou-long-expected-jesus",
     "come, thou long expected jesus",
     "Come, thou long expected Jesus, Born to set thy people free.",
     "Advent hymn — first line.")
hymn("o-thou-who-camest", "O Thou Who Camest from Above",
     "cw-duke-scripture-hymns-1762-vol-1",
     "o thou who camest from above",
     "O thou who camest from above, The pure celestial fire to impart.",
     "Buried in a large Duke-collection source — presence guards against silent chunk loss.")
hymn("and-are-we-yet-alive", "And Are We Yet Alive",
     "cw-duke-hymns-and-sacred-poems-1749-vol-2",
     "and are we yet alive",
     "And are we yet alive, And see each other's face? Glory and thanks to Jesus give For his almighty grace.",
     "The Methodist conference hymn.")
hymn("depth-of-mercy", "Depth of Mercy", "cw-depth-of-mercy",
     "depth of mercy! can there be",
     "Depth of mercy! can there be Mercy still reserved for me?",
     "First line + wording.")
hymn("charge-to-keep", "A Charge to Keep I Have", "cw-charge-to-keep",
     "a charge to keep i have",
     "A charge to keep I have, A God to glorify, A never-dying soul to save, And fit it for the sky.",
     "First stanza intact.")
hymn("knowledge-and-vital-piety", "Come, Father, Son, and Holy Ghost (Unite the Pair)",
     "cw-hymns-1780",
     "knowledge and vital piety",
     "Unite the pair so long disjoined, Knowledge and vital piety.",
     "The couplet later adopted as a university motto.")
hymn("help-us-to-help-each-other", "All Praise to Our Redeeming Lord",
     "cw-hymns-1780",
     "help us to help each other, lord",
     "Help us to help each other, Lord, Each other's cross to bear.",
     "Charles Wesley on social holiness.")
hymn("universal-redemption-horrible-decree", "Hymns on God's Everlasting Love (Universal Redemption)",
     "cw-universal-redemption",
     "horrible decree confound",
     "The HORRIBLE DECREE confound, Enlarge thy people's heart!",
     "Charles echoing John's anti-predestination stance in verse.")

# ============================== MISSING-CONTENT PROBES ==============================
add(id="no-holiness-but-social", author="john-wesley",
    work="Preface to Hymns and Sacred Poems (1739)",
    reference="Preface to Hymns and Sacred Poems (1739)",
    source_id="(preface not yet ingested)",
    anchor="no holiness but social",
    canonical="The Gospel of Christ knows of no religion but social; no holiness but social holiness.",
    catches="Wesley's social-holiness maxim. Baseline: ABSENT — a known-authentic line the corpus is missing.",
    notes="Per Wilson: this is from the 1739 Hymns preface, NOT the Journal. Currently 0 hits; flags a real content gap to fill, not an OCR error.")

# ---------------------------------------------------------------------------
# write + baseline report
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for s in S:
        f.write(json.dumps(s, ensure_ascii=False) + "\n")

print(f"Wrote {len(S)} sentinels -> {os.path.relpath(OUT, ROOT)}\n")

# Baseline: does the anchor currently locate as expected?
locate_fail, ok = [], 0
for s in S:
    hits = anywhere(s["anchor"])
    if s["expect"] == "present":
        if hits:
            ok += 1
        else:
            locate_fail.append(s)
    else:  # absent
        if hits:
            locate_fail.append(s)
        else:
            ok += 1

print(f"BASELINE anchor-locate: {ok}/{len(S)} as-expected, {len(locate_fail)} flagged\n")
if locate_fail:
    print("Flagged at baseline (the net the cleanup phases must close):")
    for s in locate_fail:
        why = "MISSING (present-expected, 0 hits)" if s["expect"] == "present" else "CONTAMINATION (absent-expected, FOUND)"
        print(f"  - {s['id']:38s} {why}  [{s.get('notes','') or s['catches'][:50]}]")
