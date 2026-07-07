"""Build metadata/swi-golden-set.jsonl — the SWI v2 calibration/regression set.

Phase 2a of plans/2026-07-07-swi-v2-ocr-cleanup-verification.md.

~40 texts with an expected overall-score RANGE and a one-line rationale each.
This is the ground truth that replaces user feedback (there is none worth
keeping) and becomes the regression suite for every rubric change: scripts/
swi_eval.py runs the judge over it and fails if any bucket drifts out of range.

Buckets (and why each exists):
  wesley-core            — Wesley/Charles at full strength                 85-100
  refuting-calvinism     — THE acid test: Calvinist vocab, Wesleyan intent 85-100
  wesleyan-tradition     — Fletcher, hymns, doctrinal standards, MODERN    60-95
  grace-dense-reformed   — warm grace-language inside an election frame    10-40
  adjacent-christian     — sincere, orthodox, but not Wesleyan             30-65
  counter-advocacy       — antinomian/works/quietist ADVOCACY             10-30
  control                — secular / non-Christian                          0-20

The hard cases are deliberate: grace-dense-reformed (Spurgeon, Whitefield's
actual reply to Wesley) would fool a vocabulary counter; the MODERN wesleyan
entries have zero 18th-c. diction and must still score high; the refutation
entries are dense in the very frameworks they attack.

`expected_counter` records the counter-indicator stance the judge SHOULD return
where that judgment is the point of the entry (advocacy vs refutation vs absent)
— swi_eval.py checks it alongside the score.

Wesley entries pull real text from the corpus by passage id (single source of
truth). Non-Wesley entries are inline: public-domain quotations where marked
"quoted", and faithful representative compositions where marked "representative"
(theologically accurate to the named position; not a verbatim citation).

Usage: python3 scripts/build_golden_set.py
"""
import json
from pathlib import Path

BASE = Path(__file__).parent.parent
CORPUS = BASE / "chunked" / "cleaned_passages.jsonl"
OUT = BASE / "metadata" / "swi-golden-set.jsonl"

corpus = {}
with open(CORPUS, encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        corpus[d["id"]] = d

entries = []


def from_corpus(gid, passage_id, bucket, lo, hi, rationale, expected_counter=None):
    p = corpus.get(passage_id)
    if p is None:
        raise SystemExit(f"golden-set: corpus passage {passage_id} not found")
    entries.append({
        "id": gid, "bucket": bucket,
        "source": f"{p['source_title']} (corpus: {passage_id})",
        "expected_min": lo, "expected_max": hi,
        "expected_counter": expected_counter or {},
        "rationale": rationale,
        "text": p["text"],
    })


def inline(gid, bucket, lo, hi, source, rationale, text, expected_counter=None):
    entries.append({
        "id": gid, "bucket": bucket, "source": source,
        "expected_min": lo, "expected_max": hi,
        "expected_counter": expected_counter or {},
        "rationale": rationale,
        "text": text.strip(),
    })


# ─────────────────────────── WESLEY CORE (85-100) ───────────────────────────
from_corpus("gs-wesley-justification", "jw-sermon-005-007", "wesley-core", 85, 100,
    "Justification by faith of the ungodly — grace to sinners 'of every kind, of every degree'.")
from_corpus("gs-wesley-new-birth", "jw-sermon-045-001", "wesley-core", 82, 100,
    "The New Birth grounded in the image of God — experiential + scriptural.")
from_corpus("gs-wesley-scripture-way", "jw-sermon-043-005", "wesley-core", 85, 100,
    "Scripture Way of Salvation — faith receiving Christ as sanctification, the full ordo.")
from_corpus("gs-wesley-perfection", "jw-treatise-plain-account-of-christian-perfection-010",
    "wesley-core", 85, 100,
    "Plain Account of Christian Perfection — the Wesleyan distinctive at its source.")
from_corpus("gs-wesley-character-methodist", "jw-character-005", "wesley-core", 82, 100,
    "Character of a Methodist — religion is not in outward duties but love of God and neighbour.")
from_corpus("gs-wesley-marks-new-birth", "jw-sermon-018-005", "wesley-core", 80, 100,
    "Marks of the New Birth — the born-of-God do not continue in sin (against antinomianism).",
    expected_counter={"antinomian": "refutation"})

# ─────────────────── CATHOLIC SPIRIT + SOCIAL HOLINESS (Wesley) ──────────────
from_corpus("gs-wesley-catholic-spirit", "jw-catholic-spirit-008", "wesley-core", 85, 100,
    "Catholic Spirit — love across differing opinions and modes of worship; the dimension's namesake.")
from_corpus("gs-wesley-general-rules", "jw-general-rules-001", "wesley-core", 78, 100,
    "General Rules — do no harm / do good / attend the ordinances; social holiness codified.")
from_corpus("gs-wesley-means-of-grace", "jw-means-of-grace-001", "wesley-core", 78, 100,
    "The Means of Grace — refutes the stillness/quietist rejection of the ordinances.",
    expected_counter={"quietist": "refutation"})

# ───────────────────────── REFUTING CALVINISM (85-100) ──────────────────────
from_corpus("gs-freegrace-thesis", "jw-free-grace-000", "refuting-calvinism", 85, 100,
    "Free Grace opening — grace 'free for all'; opposing predestination head-on.",
    expected_counter={"calvinist": "refutation"})
from_corpus("gs-freegrace-horrible-decree", "jw-free-grace-011", "refuting-calvinism", 85, 100,
    "'The horrible decree' — the acid test v1 needed a special penalty-cap for.",
    expected_counter={"calvinist": "refutation"})
from_corpus("gs-predestination-calmly", "jw-treatise-predestination-calmly-considered-003",
    "refuting-calvinism", 82, 100,
    "Predestination Calmly Considered — election implies reprobation; dense Calvinist vocab, Wesleyan intent.",
    expected_counter={"calvinist": "refutation"})
from_corpus("gs-charles-universal-redemption", "cw-universal-redemption-full",
    "refuting-calvinism", 82, 100,
    "Charles Wesley's 'Universal Redemption' — 'mercy for all'; the horrible decree confounded, in verse.",
    expected_counter={"calvinist": "refutation"})

# ─────────────────────── WESLEYAN TRADITION (60-95) ─────────────────────────
from_corpus("gs-charles-and-can-it-be", "cw-hymns-1780-109", "wesleyan-tradition", 78, 100,
    "'And Can It Be' — assurance, universal atonement, experiential grace in Charles's hymnody.")
from_corpus("gs-charles-love-divine", "cw-love-divine-full", "wesleyan-tradition", 78, 100,
    "'Love Divine' — perfect love, entire sanctification ('pure and spotless let us be') as prayer.")

inline("gs-articles-of-religion", "wesleyan-tradition", 62, 85,
    "Methodist Articles of Religion, Art. IX (quoted, public domain)",
    "Standard Methodist doctrine on justification — orthodox, grace-based, but a bare confessional statement.",
    """We are accounted righteous before God only for the merit of our Lord and \
Saviour Jesus Christ, by faith, and not for our own works or deservings. \
Wherefore, that we are justified by faith only is a most wholesome doctrine, \
and very full of comfort.""")

inline("gs-fletcher-antinomianism", "wesleyan-tradition", 72, 95,
    "John Fletcher, Checks to Antinomianism (representative)",
    "Wesley's designated successor refuting antinomianism — a refutation entry, should score high.",
    """Some cry, 'Grace, grace!' and by it understand a licence to sin — as if the \
blood of Christ were shed to purchase us liberty to break His law. But the grace \
that justifies is the same grace that sanctifies; it does not abolish the \
righteousness of the law, but writes it upon the heart. He that is truly \
justified is made a new creature, walking not after the flesh but after the \
Spirit; and he that continues wilfully in sin, pleading his election as a cloak, \
deceives his own soul, for without holiness no man shall see the Lord.""",
    expected_counter={"antinomian": "refutation"})

inline("gs-modern-wesleyan-sermon", "wesleyan-tradition", 65, 92,
    "Modern-idiom Wesleyan sermon (representative — bias test)",
    "Genuinely Wesleyan theology in wholly contemporary English; MUST score high despite zero archaic diction.",
    """Here's the good news, and it's for every single person in this room, no \
exceptions: God was already reaching for you long before you ever thought to \
reach back. That first flicker of wanting something more — that was grace, \
already at work. You don't have to clean yourself up first. You don't have to \
earn it. You just have to say yes. And here's the part we sometimes miss: God \
doesn't just forgive you and leave you where you are. God actually changes you \
— slowly, really, from the inside — until love starts to crowd out the fear and \
the resentment and the self-obsession, until one day you look up and find you \
actually love the people you used to just tolerate. That's the whole point. Not \
a ticket to heaven you file away, but a heart remade. And it doesn't happen \
alone on your couch. It happens in a community, in showing up for each other, in \
feeding people and sitting with the sick and doing the ordinary hard work of \
loving your neighbor.""")

inline("gs-modern-social-holiness", "wesleyan-tradition", 60, 88,
    "Modern social-holiness paragraph (representative)",
    "Social holiness / works of mercy in contemporary idiom; tests the social dimension without archaic vocab.",
    """There is no such thing as a private Christianity. You cannot love God and \
be indifferent to the person going hungry three streets over. Holiness that \
stays inside your own head, that never costs you anything, that never shows up \
at the shelter or the jail or the hospital bed, is not holiness at all — it is \
just religious feeling. We are saved together or not at all, and the proof of a \
changed heart is a life poured out for the poor, the sick, the imprisoned, and \
the stranger.""")

# ─────────────────── GRACE-DENSE BUT REFORMED (10-40) ───────────────────────
# These would fool a vocabulary counter: warm, grace-saturated — but the grace
# runs inside unconditional election. calvinist = ADVOCACY.
inline("gs-westminster-election", "grace-dense-reformed", 8, 30,
    "Westminster Confession of Faith III.3 (quoted, public domain)",
    "Double predestination stated confessionally — the Reformed frame Wesley rejected.",
    """By the decree of God, for the manifestation of His glory, some men and \
angels are predestinated unto everlasting life, and others foreordained to \
everlasting death. These angels and men, thus predestinated and foreordained, \
are particularly and unchangeably designed; and their number is so certain and \
definite that it cannot be either increased or diminished.""",
    expected_counter={"calvinist": "advocacy"})

inline("gs-calvin-predestination", "grace-dense-reformed", 8, 30,
    "Calvin, Institutes III.21.5 (quoted, public domain)",
    "Predestination at its source — eternal life foreordained for some, damnation for others.",
    """We call predestination God's eternal decree, by which He determined with \
Himself what He willed to become of each man. For all are not created in equal \
condition; rather, eternal life is foreordained for some, eternal damnation for \
others. Therefore, as any man has been created to one or the other of these \
ends, we speak of him as predestined to life or to death.""",
    expected_counter={"calvinist": "advocacy"})

inline("gs-spurgeon-sovereign-grace", "grace-dense-reformed", 12, 38,
    "C. H. Spurgeon on sovereign electing grace (representative)",
    "Intensely warm, grace-drenched, experiential — yet the grace is particular and electing. The key discriminator.",
    """Oh, the sweetness of free grace! I love to preach it, for it lays the \
sinner in the dust and lifts the Lord on high. Salvation is of the Lord from \
first to last. He chose His people before the foundation of the world, not for \
anything He foresaw in them, but of His own sovereign good pleasure; and those \
whom He chose, He redeemed with precious blood — not the whole race of Adam, but \
His own elect, the sheep given Him by the Father. And every one of them He will \
draw with cords of love, and not one shall be lost, for the purpose of God \
according to election shall stand. If you are saved, give all the glory to \
distinguishing grace, which passed by thousands and lighted upon you.""",
    expected_counter={"calvinist": "advocacy"})

inline("gs-whitefield-reply", "grace-dense-reformed", 12, 38,
    "George Whitefield's reply to Wesley's 'Free Grace' (representative)",
    "Whitefield — warm evangelical, revival preacher — defending the election Wesley attacked. Advocacy, not refutation.",
    """Dear and honoured sir, you think God's free grace is dishonoured by the \
doctrine of election; I say it is most gloriously exalted by it. What is more \
free than for God to choose whom He will, out of a fallen mass that deserved \
nothing but wrath? Universal redemption I cannot preach, for if Christ died \
alike for all, and yet all are not saved, then His blood is spilt in vain for \
multitudes. No — He laid down His life for the sheep, and the redeemed are a \
number no man can number, chosen in Him before the world began. This election \
is the very fountain of comfort, for it hangs my salvation not on my poor \
changeable will but on God's unchangeable love.""",
    expected_counter={"calvinist": "advocacy"})

inline("gs-canons-dort", "grace-dense-reformed", 8, 30,
    "Canons of Dort, First & Second Heads (representative)",
    "Unconditional election and definite (limited) atonement stated together.",
    """Election is the unchangeable purpose of God, whereby, before the foundation \
of the world, out of the whole human race fallen by their own fault, He has, \
according to the most free good pleasure of His will, chosen a certain number of \
persons to salvation. It was the will of God that Christ, by the blood of the \
cross, should effectually redeem out of every people those, and those only, who \
were from eternity chosen to salvation and given to Him by the Father.""",
    expected_counter={"calvinist": "advocacy"})

# ─────────────────────── ADJACENT CHRISTIAN (30-65) ─────────────────────────
inline("gs-aquinas-grace", "adjacent-christian", 35, 60,
    "Thomas Aquinas, Summa Theologiae I-II (representative)",
    "Rich on grace, but scholastic and infused-habit framed — orthodox, not Wesleyan-distinctive.",
    """Grace, as a quality, is said to act upon the soul not by way of efficient \
cause, but formally, as whiteness makes a thing white. For the light of grace, \
which is a participation of the divine nature, is poured into the soul as a \
habitual gift, whereby the powers of the soul are healed and elevated to acts \
that merit eternal life. Yet no one can merit the first grace, for merit \
presupposes grace; the beginning of our justification is from God moving the \
will inwardly.""")

inline("gs-bcp-collect-purity", "adjacent-christian", 40, 65,
    "Collect for Purity, Book of Common Prayer (quoted, public domain)",
    "A prayer Wesley himself used weekly; devotional, aims at perfect love — but liturgical, not distinctively Wesleyan.",
    """Almighty God, unto whom all hearts be open, all desires known, and from \
whom no secrets are hid: Cleanse the thoughts of our hearts by the inspiration \
of thy Holy Spirit, that we may perfectly love thee, and worthily magnify thy \
holy Name; through Christ our Lord. Amen.""")

inline("gs-kempis-imitation", "adjacent-christian", 40, 62,
    "Thomas à Kempis, Imitation of Christ, Bk I (representative)",
    "Deeply devotional/experiential — Wesley abridged it — but monastic, world-renouncing, no social holiness.",
    """What doth it profit thee to enter into deep discussion concerning the Holy \
Trinity, if thou lack humility, and be thus displeasing to the Trinity? Verily \
high words make not a man holy and just; but a virtuous life maketh him dear to \
God. I had rather feel contrition than be skilful in the definition thereof. \
Vanity of vanities, all is vanity, save to love God and Him only to serve. This \
is the highest wisdom: to cast the world behind us, and to reach forward to the \
heavenly kingdom.""")

inline("gs-luther-freedom", "adjacent-christian", 42, 65,
    "Martin Luther, Freedom of a Christian (representative)",
    "Justification by faith, experiential liberty — Aldersgate's own root — but no perfection, and law undervalued.",
    """A Christian man is the most free lord of all, and subject to none; a \
Christian man is the most dutiful servant of all, and subject to every one. \
Faith alone, without works, justifies, frees, and saves. The moment you begin to \
believe, you learn that all things in you are altogether blameworthy, sinful, \
and damnable, and that Christ is your righteousness, given wholly as a gift. \
This faith cannot exist along with works; if you imagine you can be justified by \
anything you do, you make Christ of no value.""")

inline("gs-athanasius-theosis", "adjacent-christian", 45, 68,
    "Athanasius, On the Incarnation 54 (representative)",
    "Deification/theosis — the Eastern perfection tradition Wesley loved; the nearest adjacent boundary, high side.",
    """For the Son of God became man, that we might become god. He manifested \
Himself by a body, that we might receive an idea of the invisible Father; and He \
endured the insolence of men, that we might inherit incorruption. For He was \
made man that we might be made divine; and He revealed Himself through a body \
that we might receive knowledge of the unseen Father; and He endured the \
shame from men that we might inherit immortality.""")

# ──────────── COUNTER-INDICATOR ADVOCACY (antinomian/works/quietist) ─────────
inline("gs-antinomian-advocacy", "counter-advocacy", 8, 28,
    "High-antinomian teaching (representative)",
    "Advocates that the believer is free from the law and need not regard holiness — Wesley's lifelong enemy.",
    """You are complete in Christ, and nothing you do or fail to do can add to or \
take from your standing. The law was nailed to the cross; it has no more claim \
on the believer. Therefore trouble not yourself about your sins — to look at \
your own conduct at all is to fall from grace into legal bondage. God sees no \
sin in His people; He beholds them only in the spotless righteousness of \
Christ. Rest wholly there, and never let the preaching of duties and \
commandments rob you of your assurance.""",
    expected_counter={"antinomian": "advocacy"})

inline("gs-works-righteousness-advocacy", "counter-advocacy", 8, 30,
    "Moralistic self-salvation (representative)",
    "Salvation earned by good deeds and self-improvement — the opposite error; justification by works.",
    """Heaven is the reward of a life well lived. God helps those who help \
themselves, and in the end each of us is weighed in the balance of our own \
deeds. If your good outweighs your bad, if you have been decent to your \
neighbours and diligent in your duties, you have earned your place. Salvation is \
not a gift to be received but a wage to be worked for; make yourself worthy, \
better yourself day by day, and trust that an honest ledger will open the gates \
to you at the last.""",
    expected_counter={"works_righteousness": "advocacy"})

inline("gs-quietist-stillness", "counter-advocacy", 8, 30,
    "Moravian 'stillness' / quietist teaching (representative)",
    "Cease from the ordinances and wait passively — the exact doctrine Wesley broke with Molther over.",
    """Be still, and do nothing. So long as you have not the full assurance of \
faith, you are only a hypocrite in using the means of grace. Do not go to \
church, do not communicate, do not read the Scripture, do not pray, do not do \
any outward work — for to do so before you believe is to build your own \
righteousness. Simply be still, and wait for Christ to work faith in you. All \
striving, all ordinances, all endeavour, is of the flesh; the one thing needful \
is to cease from your own working and be quiet.""",
    expected_counter={"quietist": "advocacy"})

# ─────────────────────────── CONTROL (0-20) ─────────────────────────────────
inline("gs-control-news", "control", 0, 12,
    "Neutral news wire copy (representative)",
    "Ordinary journalism — no theological content at all; a floor anchor.",
    """The transit authority announced Tuesday that the downtown line will close \
for scheduled maintenance over the weekend, with shuttle buses running every \
fifteen minutes between the affected stations. Officials said the work, budgeted \
at 4.2 million dollars, is expected to reduce delays that have frustrated \
commuters since the spring. Ridership on the line has recovered to roughly \
eighty percent of its pre-pandemic level, according to figures released by the \
agency.""")

inline("gs-control-selfhelp", "control", 2, 18,
    "Motivational self-help (representative)",
    "Uses 'transformation', 'purpose', even 'grace' loosely — but wholly secular; tests that uplift is not Wesleyan.",
    """You have within you everything you need to become your best self. \
Transformation begins the moment you decide to show up for your own life. \
Release what no longer serves you, set a bold intention, and trust the journey. \
Every day is a fresh chance to align with your purpose and manifest the \
abundance you deserve. Give yourself grace, honour your growth, and remember: \
you are enough, exactly as you are.""")

inline("gs-control-technical", "control", 0, 8,
    "Technical documentation (representative)",
    "Pure procedural prose — a hard floor.",
    """To configure the connection pool, set the maximum pool size in the \
application properties file and restart the service. The default idle timeout is \
thirty seconds; connections exceeding this threshold are returned to the pool. \
If the pool is exhausted, incoming requests will block until a connection \
becomes available or the request timeout is reached, whichever comes first. \
Enable query logging only in non-production environments, as it introduces \
measurable latency.""")

inline("gs-control-marcus-aurelius", "control", 5, 22,
    "Marcus Aurelius, Meditations II.1 (representative)",
    "Morally serious, even devout-sounding, but pagan Stoic — Wesley himself cited 'Poor Antoninus!'; a non-Christian control.",
    """Begin the morning by saying to thyself, I shall meet with the busybody, \
the ungrateful, arrogant, deceitful, envious, unsocial. All these things happen \
to them by reason of their ignorance of what is good and evil. But I who have \
seen the nature of the good that it is beautiful, and of the bad that it is \
ugly, can neither be injured by any of them, nor be angry with my kinsman. For \
we are made for co-operation, like the feet, the hands, the eyelids.""")

# ── write ──
OUT.parent.mkdir(exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

from collections import Counter
buckets = Counter(e["bucket"] for e in entries)
print(f"Wrote {len(entries)} golden-set entries -> {OUT.relative_to(BASE)}")
for b, n in buckets.most_common():
    print(f"  {b:24s} {n}")
short = [e["id"] for e in entries if len(e["text"].split()) < 60]
if short:
    print(f"\nNote: {len(short)} entries under 60 words (scored less reliably per rubric): {short}")
