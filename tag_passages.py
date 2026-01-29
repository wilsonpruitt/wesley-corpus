#!/usr/bin/env python3
"""
Script to analyze and tag untagged passages in passages.jsonl
using aggressive keyword and context matching for Wesley theological themes.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

# Define keyword patterns for each theme
THEME_KEYWORDS = {
    'works-piety': [
        r'\b(law|commandment|duty|obey|righteousness|holy|holiness|virtue|'
        r'discipline|prayer|fasting|devotion|morality|ethical|virtue)\b',
        r'\b(do|perform|fulfill|accomplish|keep|maintain)\s+(our|your|his|the)\s+(duty|law|commandment)',
    ],
    'sanctifying-grace': [
        r'\b(sanctif|sancti|holiness|holy|pure|purity|entire|perfection|'
        r'complete|wholeness|transformation|renewal)\b',
        r'\b(grace|spirit)\s+(work|sanctif|transform|renew)',
    ],
    'justifying-grace': [
        r'\b(faith|believe|trust|justified|justif|salvation|saved|redeem|'
        r'pardon|forgiven|forgiveness|acquitted|ransomed|ransom)\b',
        r'\b(Christ|Jesus)\s+(righteousness|atonement|sacrifice)',
    ],
    'prevenient-grace': [
        r'\b(prevent|quicken|awaken|stir|move|draw|attract|enable|'
        r'before|prior|antecedent|preceding|withstand|resist|grace)\b',
        r'\b(grace|spirit)\s+(move|work|prevent|draw)',
    ],
    'free-will': [
        r'\b(free|freedom|will|choose|choice|liberty|agent|agency|autonomy|'
        r'reason|rational|intellect|mind|understanding)\b',
        r'\b(power|ability)\s+(to|of)\s+(choose|act|decide)',
    ],
    'means-of-grace': [
        r'\b(means|ordinance|sacrament|pray|prayer|worship|fast|fast|'
        r'scripture|scripture|word|communion|eucharist|bread|wine|'
        r'baptism|method|instrument|walk|employ|employ|bounteous)\b',
        r'\b(through|by|via)\s+(prayer|worship|scripture|sacrament)',
    ],
    'social-holiness': [
        r'\b(social|community|neighbor|love|charity|compassion|care|'
        r'relationship|fellowship|unity|together|mutual|common|'
        r'brotherhood|sisterhood)\b',
        r'\b(love)\s+(neighbor|one\s+another|thy\s+neighbor)',
    ],
    'works-mercy': [
        r'\b(mercy|compassion|help|aid|charitable|charity|poor|hungry|'
        r'naked|stranger|slave|oppression|oppressed|freedom|justice|'
        r'injustice|inequality|suffer|suffering|widow|orphan|sick)\b',
        r'\b(do|show|give)\s+(mercy|charity|help|aid)',
    ],
    'assurance': [
        r'\b(assurance|assure|confident|confidence|certain|certainty|sure|'
        r'sureness|knowing|know|witness|testimony|spirit|proof|evidence)\b',
        r'\b(spirit)\s+(witness|testif)',
    ],
    'scriptural-authority': [
        r'\b(scripture|biblical|bible|word|word\s+of\s+god|testament|'
        r'authority|authorit|canonical|divine|truth|true)\b',
        r'\b(written|command|say)\s+(in|by|the)\s+(scripture|bible|word)',
    ],
    'catholic-spirit': [
        r'\b(catholic|universal|universal|church|unity|united|denomination|'
        r'sect|schism|divide|boundary|limit|all|every|ecumenical|inclusive)\b',
        r'\b(all|every|universal)\s+(christian|believer|person|denomination)',
    ],
    'experience': [
        r'\b(experience|experiential|feel|feeling|sense|sensation|emotion|'
        r'know|knowledge|understand|understanding|perceive|perception|encounter|'
        r'inner|inward|personal)\b',
        r'\b(my|your|his|her)\s+(experience|feeling|sense|knowledge)',
    ],
    'universal-redemption': [
        r'\b(universal|all|every|mankind|humanity|race|world|whosoever|'
        r'whomsoever|redemption|redeem|available|for\s+all|none\s+excluded|ransomed)\b',
        r'\b(redemption|saved|salvation)\s+(for|of)\s+(all|mankind|humanity)',
    ],
    'reign-of-god': [
        r'\b(kingdom|reign|eternal|heaven|hell|judgment|judg|angel|demon|'
        r'satan|devil|death|hell|damnation|glory|everlast|immortal|divine|god|scars|rapture|token|passion)',
        r'\b(kingdom|reign)\s+(of|in)\s+(god|heaven|christ)',
    ],
    'primitive-christianity': [
        r'\b(primitive|ancient|early|apostolic|apostle|disciple|original|'
        r'first|church\s+father|early\s+christian)\b',
        r'\b(early|first|primitive)\s+(church|christian|apostle)',
    ],
    'communion': [
        r'\b(communion|eucharist|sacrament|lord|table|supper|bread|wine|'
        r'partake|memorial|covenant)\b',
        r'\b(communion|eucharist|supper)\s+(of|with|the)',
    ],
    'repentance': [
        r'\b(repent|repentance|penitent|penitence|contrition|sorrow|regret|'
        r'sin|guilt|guilty|conviction|convicted|remorse|turn|turning|conversion|'
        r'withstand|provok|deny|denied|crucif|profan|shame)\b',
        r'\b(turn|repent|convert)\s+(from|to|back)\s+(sin|god|christ)',
    ],
    'trinity': [
        r'\b(trinity|triune|threefold|father|son|holy\s+ghost|holy\s+spirit|'
        r'three|persons|god|godhead)\b',
        r'\b(father|son|spirit)\s+(and|or)',
    ],
    'christology': [
        r'\b(christ|jesus|lord|savior|messiah|incarnat|god\s+become|divine\s+human|'
        r'atonement|sacrifice|blood|cross|redemption|resurrection|risen|passion|scars|dazzling|ransomed)\b',
        r'\b(jesus|christ|lord|savior)',
    ],
    'pneumatology': [
        r'\b(spirit|holy\s+ghost|holy\s+spirit|pentecost|spiritual|gift|'
        r'filled|filling|anointed|witness|testimony|power|wind|breath)\b',
        r'\b(holy\s+(ghost|spirit)|spirit|pneuma)',
    ],
}

def is_untagged(passage):
    """Check if a passage is untagged."""
    themes = passage.get('themes', [])
    return not themes or themes is None or (isinstance(themes, list) and len(themes) == 0)

def match_keywords(text, patterns):
    """Check if any keyword pattern matches in the text."""
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower):
            return True
    return False

def analyze_passage(text):
    """Analyze a passage and suggest themes based on keyword matching."""
    assigned_themes = []
    theme_scores = {}

    # Calculate match score for each theme
    for theme, patterns in THEME_KEYWORDS.items():
        matches = 0
        for pattern in patterns:
            # Count all matches for this pattern
            matches += len(re.findall(pattern, text.lower()))

        if matches > 0:
            theme_scores[theme] = matches

    # Sort themes by score and take top 3
    sorted_themes = sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)

    # Assign 1-3 themes
    for theme, score in sorted_themes[:3]:
        if score > 0:
            assigned_themes.append(theme)

    return assigned_themes

def main():
    input_file = Path('/Users/wilsonpruitt/Documents/Personal/wesley-corpus/chunked/passages.jsonl')

    if not input_file.exists():
        print(f"Error: File not found: {input_file}")
        return

    passages = []
    untagged_count = 0
    tagged_count = 0

    # Read the file
    print("Reading passages.jsonl...")
    with open(input_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    passage = json.loads(line)
                    passages.append(passage)
                    if is_untagged(passage):
                        untagged_count += 1
                except json.JSONDecodeError as e:
                    print(f"Error parsing line {line_num}: {e}")

    print(f"Total passages: {len(passages)}")
    print(f"Untagged passages: {untagged_count}")
    print()

    # Analyze and tag untagged passages
    print("Analyzing untagged passages...")
    newly_tagged = 0
    theme_assignment_count = defaultdict(int)

    for passage in passages:
        if is_untagged(passage):
            themes = analyze_passage(passage['text'])
            if themes:
                passage['themes'] = themes
                newly_tagged += 1
                for theme in themes:
                    theme_assignment_count[theme] += 1

    # Write back to file
    print(f"Writing updated passages to file...")
    with open(input_file, 'w') as f:
        for passage in passages:
            f.write(json.dumps(passage) + '\n')

    # Report results
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Passages tagged: {newly_tagged}")
    print(f"Untagged passages remaining: {max(0, untagged_count - newly_tagged)}")
    print()
    print("Theme assignment counts:")
    for theme in sorted(THEME_KEYWORDS.keys()):
        count = theme_assignment_count[theme]
        if count > 0:
            print(f"  {theme}: {count}")

    if newly_tagged == untagged_count:
        print()
        print("SUCCESS: All untagged passages have been tagged!")
    else:
        print()
        print(f"Note: {untagged_count - newly_tagged} passages could not be matched to themes")

if __name__ == '__main__':
    main()
