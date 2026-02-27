#!/usr/bin/env python3
"""
Download Charles Wesley's Published Verse from Duke Divinity School.

Source: https://divinity.duke.edu/initiatives/wesleyan-methodist/cswt-cw-published

Downloads:
  1. ZIP archive of all original transcripts
  2. All modernized PDFs individually
"""

import os
import time
import urllib.request
import urllib.error

BASE_URL = "https://divinity.duke.edu/sites/default/files/documents"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "raw", "duke-cw-verse")

ZIP_URL = f"{BASE_URL}/Charles_Wesley_Published_Verse_%28Original%29_zipped_0.zip"

# Modernized PDFs — (filename, human-readable title)
MODERNIZED = [
    ("01_Hymns_and_Sacred_Poems_%281739%29_CW_Verse_mod.pdf", "Hymns and Sacred Poems (1739) CW Verse"),
    ("02_Universal_Redemption_%281739%29_Mod.pdf", "Universal Redemption (1739)"),
    ("03_Means_of_Grace_%281740%29_Mod.pdf", "Means of Grace (1740)"),
    ("04_Life_of_Faith_%281740%29_Mod.pdf", "Life of Faith (1740)"),
    ("05_Hymns_and_Sacred_Poems_%281740%29_mod.pdf", "Hymns and Sacred Poems (1740)"),
    ("06_Collection_of_Psalms_and_Hymns_%281741%29_CW_verse_mod.pdf", "Collection of Psalms and Hymns (1741) CW Verse"),
    ("07_Hymns_on_God%27s_Everlasting_Love_%281741%29_mod.pdf", "Hymns on God's Everlasting Love (1741)"),
    ("08_Promise_of_Sanctification_%281741%29_Mod.pdf", "Promise of Sanctification (1741)"),
    ("09_Hymns_on_God%27s_Everlasting_Love_%281742%29_mod.pdf", "Hymns on God's Everlasting Love 2nd series (1742)"),
    ("10_Hymns_and_Sacred_Poems_%281742%29_mod.pdf", "Hymns and Sacred Poems (1742)"),
    ("11_Whole_Armour_of_God_%281742%29_Mod.pdf", "Whole Armour of God (1742)"),
    ("12_Taking_of_Jericho_%20%281742%29_Mod.pdf", "Taking of Jericho (1742)"),
    ("13_Elegy_on_Robert_Jones_%281742%29_Mod.pdf", "Elegy on Robert Jones (1742)"),
    ("14_Fourteenth_Chapter_of_Isaiah_%20%281742%29_Mod.pdf", "Fourteenth Chapter of Isaiah (1742)"),
    ("15_Thanksgiving_for_Colliers_%20%281742%29_Mod.pdf", "Thanksgiving for Colliers (1742)"),
    ("16_Hymn_for_Condemned_Prisoners_%20%281742%29_Mod.pdf", "Hymn for Condemned Prisoners (1742)"),
    ("17_Psalms_%281743%29_mod.pdf", "CPH Psalms (1743)"),
    ("18_Prayer_for_Those_Convinced_of_Sin_%281743%29_Mod.pdf", "Prayer for Those Convinced of Sin (1743)"),
    ("19_Primitive_Christianity_%281743%29_Mod.pdf", "Primitive Christianity (1743)"),
    ("20_Hymn_for_Christmas_Day_%281743%29%20%281%29.pdf", "Hymn for Christmas Day (1743)"),
    ("21_Moral_and_Sacred_Poems_3-206ff_%281744%29_mod.pdf", "Moral and Sacred Poems 3:206ff (1744)"),
    ("22_Hymns_for_Times_of_Trouble_%281744%29_Mod.pdf", "Hymns for Times of Trouble (1744)"),
    ("23_Hymns_for_Times_of_Trouble_and_Persecution_%281744%29_mod.pdf", "Hymns for Times of Trouble and Persecution (1744)"),
    ("24_Bloody_Issue_%281744%29_Mod.pdf", "Bloody Issue (1744)"),
    ("25_Hymns_for_Christmas_Day_%281744%29_Mod.pdf", "Hymns for Christmas Day (1744)"),
    ("26_Act_of_Devotion_%281745%29_Mod.pdf", "Act of Devotion (1745)"),
    ("27_Hymns_on_the_Lord%27s_Supper_%281745%29_mod.pdf", "Hymns on the Lord's Supper (1745)"),
    ("28_Hymns_in_Difference_with_Moravians_%281745%29_Mod.pdf", "Hymns in Difference with Moravians (1745)"),
    ("29_Hymns_from_Jeremiah_%281745%29_Mod.pdf", "Hymns from Jeremiah (1745)"),
    ("30_Hymns_in_Word_in_Season_%281745%29_Mod.pdf", "Hymns in Word in Season (1745)"),
    ("31_Nativity_Hymns_%281745%29_Mod.pdf", "Nativity Hymns (1745)"),
    ("32_Hymns_in_Word_for_a_Protestant_%281745%29_Mod.pdf", "Hymns in Word to a Protestant (1745)"),
    ("33_Hymns_for_1745_Mod.pdf", "Hymns for 1745"),
    ("34_Funeral_Hymns_%281746%29_Mod.pdf", "Funeral Hymns (1746)"),
    ("35_Resurrection_Hymns_%281746%29_Mod.pdf", "Resurrection Hymns (1746)"),
    ("36_Ascension_Hymns_%281746%29_Mod.pdf", "Ascension Hymns (1746)"),
    ("37_Whitsunday_Hymns_%281746%29_mod.pdf", "Whitsunday Hymns (1746)"),
    ("38_Festival_Hymns_%281746%29_mod.pdf", "Festival Hymns (1746)"),
    ("39_Thanksgiving_Hymns_%281746%29_Mod.pdf", "Thanksgiving Hymns (1746)"),
    ("40_Gloria_Patri_%281746%29_Mod.pdf", "Gloria Patri (1746)"),
    ("41_Graces_%281746%29_Mod.pdf", "Graces (1746)"),
    ("42_Hymn_at_the_Sacrament_%281747%29_Mod.pdf", "Hymn at the Sacrament (1747)"),
    ("43_Person_Bearing_Testimony_%281747%29_Mod.pdf", "Person Bearing Testimony (1747)"),
    ("44_Redemption_Hymns_%281747%29_mod.pdf", "Redemption Hymns (1747)"),
    ("45_Hymns_and_Sacred_Poems_%281749%29_Vol_1_mod.pdf", "Hymns and Sacred Poems (1749) Vol 1"),
    ("46_Hymns_and_Sacred_Poems_%281749%29_Vol_2_mod.pdf", "Hymns and Sacred Poems (1749) Vol 2"),
    ("47_New_Years_Hymns_%281749%29_Mod.pdf", "New Year's Hymns (1749)"),
    ("48_Earthquake_Hymns_%281750%29_Pt_I_Mod.pdf", "Earthquake Hymns Pt I (1750)"),
    ("49_Earthquake_Hymns_%281750%29_Pt_II_Mod.pdf", "Earthquake Hymns Pt II (1750)"),
    ("50_Death_of_Thomas_Hogg_%281750%29_Mod.pdf", "Death of Thomas Hogg (1750)"),
    ("51_Epistle_to_John_Wesley_%281755%29_Mod.pdf", "Epistle to John Wesley (1755)"),
    ("52_Catholic_Love_%281755%29_Mod.pdf", "Catholic Love (1755)"),
    ("53_Hymn_on_the_Lisbon_Earthquake_%281756%29_Mod.pdf", "Hymn on the Lisbon Earthquake (1756)"),
    ("54_Hymns_for_the_Year_1756_Mod.pdf", "Hymns for the Year 1756"),
    ("55_Additional_Hymns_for_1756_Mod.pdf", "Additional Hymns for 1756"),
    ("56_Intercession_Hymns_%281758%29_Mod.pdf", "Intercession Hymns (1758)"),
    ("57_Intercession_Hymns_%281759%29_Mod.pdf", "Intercession Hymns (1759)"),
    ("58_Funeral_Hymns_%281759%29_mod.pdf", "Funeral Hymns (1759)"),
    ("59_Invasion_Hymns_%281759%29_Mod.pdf", "Invasion Hymns (1759)"),
    ("60_Hymn_for_the_People_of_Custrin_%281759%29_Mod.pdf", "Hymn for the People of Custrin (1759)"),
    ("61_Thanksgiving_Hymns_%281759%29_Mod.pdf", "Thanksgiving Hymns (1759)"),
    ("62_Hymns_for_the_Methodist_Preachers_%281760%29%20Mod.pdf", "Hymns for the Methodist Preachers (1760)"),
    ("63_Scripture_Hymns_%281762%29_Vol_1_mod.pdf", "Scripture Hymns (1762) Vol 1"),
    ("64_Scripture_Hymns_%281762%29_Vol_2_mod.pdf", "Scripture Hymns (1762) Vol 2"),
    ("65_Hymns_for_Children_%281763%29_mod.pdf", "Hymns for Children (1763)"),
    ("66_Family_Hymns_%281767%29_mod.pdf", "Family Hymns (1767)"),
    ("67_Trinity_Hymns_%281767%29_mod.pdf", "Trinity Hymns (1767)"),
    # 68 mod PDF appears to be a duplicate of 67 on the site — skip
    ("69_Hymn_for_Whitefield_%281770%29_Mod.pdf", "Hymn for Whitefield (1770)"),
    ("70_Elegy_on_Whitefield_%281771%29_Mod.pdf", "Elegy on Whitefield (1771)"),
    ("71_Epistle_to_Whitefield_%281771%29_Mod.pdf", "Epistle to Whitefield (1771)"),
    ("72_Preparation_for_Death_%281772%29_Mod.pdf", "Preparation for Death (1772)"),
    ("73_Arminian_Magazine_1778-87_mod.pdf", "Arminian Magazine (1778-87)"),
    ("74_Ode_on_Dr_Boyce_%281779%29_Mod.pdf", "Ode on Dr. Boyce (1779)"),
    ("75_Hymn_for_John_Wesley_%281779%29_Mod.pdf", "Hymn for John Wesley (1779)"),
    ("76_Tumult_Hymns_%281780%29_Mod.pdf", "Tumult Hymns (1780)"),
    ("77_Protestant_Association_%281781%29_Mod.pdf", "Protestant Association (1781)"),
    ("78_Hymns_for_the_Nation_%281781%29_Mod.pdf", "Hymns for the Nation (1781)"),
    ("79_Hymns_for_the_National_Fast_%281782%29_Mod.pdf", "Hymns for the National Fast (1782)"),
    ("80_Prayers_for_Condemned_Malefactors_%281785%29_Mod.pdf", "Prayers for Condemned Malefactors (1785)"),
    # Secondary collections
    ("80a_Hymns_and_Sacred_Poems_%281747%29_mod.pdf", "Hymns and Sacred Poems (1747)"),
    ("81_Watchnight_Hymns_%281750%29_mod.pdf", "Watchnight Hymns (1750)"),
    ("82_Answer_to_Gill_%281754%29_Mod.pdf", "Answer to Gill (1754)"),
    ("83_All_in_All_%281761%29_mod.pdf", "All in All (1761)"),
]

# Also grab the abbreviations reference
EXTRAS = [
    ("Short%20Titles%20and%20Abbreviations_2.pdf", "Short Titles and Abbreviations"),
]


def download(url, dest):
    """Download a URL to a local path. Returns True on success."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Wesley-Corpus/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(dest, "wb") as f:
                f.write(resp.read())
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"  ERROR: {e}")
        return False


def main():
    os.makedirs(os.path.join(OUT_DIR, "originals-zip"), exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "modernized"), exist_ok=True)

    # 1. Download ZIP of all originals
    zip_dest = os.path.join(OUT_DIR, "originals-zip", "Charles_Wesley_Published_Verse_Original.zip")
    if os.path.exists(zip_dest):
        print(f"SKIP (exists): {zip_dest}")
    else:
        print("Downloading originals ZIP archive...")
        if download(ZIP_URL, zip_dest):
            size_kb = os.path.getsize(zip_dest) / 1024
            print(f"  OK ({size_kb:.0f} KB)")
        else:
            print("  FAILED")

    # 2. Download all modernized PDFs
    success = 0
    skipped = 0
    failed = 0
    total = len(MODERNIZED) + len(EXTRAS)

    for items, subdir in [(MODERNIZED, "modernized"), (EXTRAS, "modernized")]:
        for filename, title in items:
            dest = os.path.join(OUT_DIR, subdir, urllib.request.url2pathname(filename))
            if os.path.exists(dest):
                print(f"SKIP (exists): {title}")
                skipped += 1
                continue

            url = f"{BASE_URL}/{filename}"
            print(f"[{success + failed + skipped + 1}/{total}] {title}...")
            if download(url, dest):
                size_kb = os.path.getsize(dest) / 1024
                print(f"  OK ({size_kb:.0f} KB)")
                success += 1
            else:
                failed += 1

            # Be polite to Duke's server
            time.sleep(0.5)

    print(f"\nDone! {success} downloaded, {skipped} skipped, {failed} failed.")
    print(f"Files saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
