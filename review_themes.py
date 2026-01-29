#!/usr/bin/env python3
"""
Quality review and fixing of theme assignments in the Wesley corpus.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

# Define theme-specific content validators
def has_catholic_spirit_content(text):
    """Check if text actually discusses unity, ecumenism, denominations, tolerance."""
    # Should mention unity, denominations, ecumenism, tolerance between groups
    patterns = [
        r'\bunity\b',
        r'\bdenominational\b|denomination',
        r'\becumenical\b|ecumenism',
        r'\btolerance\b|tolerate',
        r'\bdifferent\s+(churches|denominations|sects)',
        r'\bbrethren\b.*\b(different|other|various)',
        r'\bopinions?\b.*\b(harmless|innocent)',
        r'\b(baptist|methodist|presbyterian|roman\s+catholic|church\s+of\s+england)\b',
        r'\bspirit.*of\s+candor',
        r'\bno\s+opinion\b.*\b(essential|salvation)',
    ]
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in patterns)

def has_communion_content(text):
    """Check if text discusses the Lord's Supper/Eucharist specifically."""
    patterns = [
        r'\blord\'s\s+supper\b',
        r'\beucharist\b',
        r'\bcommunion\b.*\b(table|bread|wine|supper)',
        r'\bbread\b.*\b(wine|cup)',
        r'\bsacrament\b',
        r'\bmemorially\b',
        r'\btable\s+(of\s+)?lord',
        r'\bbreaking\s+of\s+bread\b',
    ]
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in patterns)

def has_trinity_content(text):
    """Check if text discusses the Trinity doctrine specifically."""
    patterns = [
        r'\btrinity\b',
        r'\bfather.*\bson.*\bspirit\b',
        r'\bfather.*\bson.*\bholy\s+ghost\b',
        r'\bthree.*persons?\b.*\b(god|godhead)',
        r'\bone\s+essence.*three\s+persons',
        r'\bsubstance.*three\s+persons',
    ]
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in patterns)

def has_universal_redemption_content(text):
    """Check if text discusses Christ dying for all or against limited atonement."""
    patterns = [
        r'\bchrist.*died.*\ball\b',
        r'\tall\s+(mankind|men|people).*redeemed',
        r'\buniversal\s+(redemption|atonement)',
        r'\blimited\s+atonement\b',
        r'\bwould\s+have\s+all\s+men\s+be\s+saved',
        r'\bfor\s+sinners\b.*\ball',
        r'\bfor\s+the\s+world\b',
        r'\bpropitiation\b.*\bworld\b',
        r'\bwhosoever\s+believeth\b',
    ]
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in patterns)

def has_pneumatology_content(text):
    """Check if text specifically discusses the Holy Spirit doctrine."""
    patterns = [
        r'\bholy\s+(spirit|ghost)\b',
        r'\bspirit.*bear(s|eth)\s+witness',
        r'\bspirit.*seal\b',
        r'\bspirit.*comforter\b',
        r'\banointing.*\bspirit\b',
    ]
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in patterns)

def extract_keywords(text):
    """Extract key terms from text for analysis."""
    keywords = []
    text_lower = text.lower()

    keyword_patterns = {
        'grace': r'\bgrace\b',
        'faith': r'\bfaith\b',
        'christ': r'\bchrist\b|jesus\b',
        'spirit': r'\bspirit\b',
        'salvation': r'\bsalvation\b',
        'works': r'\bworks?\b',
        'mercy': r'\bmercy\b',
        'holiness': r'\bholiness\b',
        'perfect': r'\bperfect\b',
        'sanctif': r'\bsanctif',
        'repent': r'\brepent',
        'gospel': r'\bgospel\b',
        'scripture': r'\bscripture\b|bible\b',
        'assurance': r'\bassurance\b',
    }

    for keyword, pattern in keyword_patterns.items():
        if re.search(pattern, text_lower):
            keywords.append(keyword)

    return keywords

def content_match_themes(text, themes):
    """Analyze if themes match text content."""
    issues = []

    # Check for potentially misapplied themes
    if 'catholic-spirit' in themes:
        if not has_catholic_spirit_content(text):
            issues.append({
                'type': 'over-tagged',
                'theme': 'catholic-spirit',
                'reason': 'No mention of unity, denominations, tolerance, or ecumenism'
            })

    if 'communion' in themes:
        if not has_communion_content(text):
            issues.append({
                'type': 'over-tagged',
                'theme': 'communion',
                'reason': 'No mention of Lord\'s Supper, eucharist, bread/wine, or sacrament'
            })

    if 'trinity' in themes:
        if not has_trinity_content(text):
            issues.append({
                'type': 'over-tagged',
                'theme': 'trinity',
                'reason': 'No specific discussion of Trinity doctrine'
            })

    if 'universal-redemption' in themes:
        if not has_universal_redemption_content(text):
            issues.append({
                'type': 'over-tagged',
                'theme': 'universal-redemption',
                'reason': 'No discussion of Christ dying for all or universal salvation'
            })

    if 'pneumatology' in themes:
        if not has_pneumatology_content(text):
            issues.append({
                'type': 'over-tagged',
                'theme': 'pneumatology',
                'reason': 'No specific discussion of the Holy Spirit'
            })

    return issues

def suggest_themes_from_content(text):
    """Suggest appropriate themes based on content."""
    suggested = []
    text_lower = text.lower()

    # Check for various themes
    if re.search(r'\bjustif(y|ication)\b', text_lower):
        suggested.append('justifying-grace')

    if re.search(r'\bsanctif', text_lower):
        suggested.append('sanctifying-grace')

    if re.search(r'\bperfect\b', text_lower):
        suggested.append('christian-perfection')

    if re.search(r'\b(free\s+)?will\b', text_lower):
        suggested.append('free-will')

    if re.search(r'\b(prayer|sacrament|means)\b', text_lower):
        suggested.append('means-of-grace')

    if re.search(r'\bsocial\b|community\b', text_lower):
        suggested.append('social-holiness')

    if re.search(r'\b(mercy|compassion|charity)\b', text_lower):
        suggested.append('works-mercy')

    if re.search(r'\b(worship|devotion|pray)\b', text_lower):
        suggested.append('works-piety')

    if re.search(r'\bassurance\b', text_lower):
        suggested.append('assurance')

    if re.search(r'\bscripture\b|bible\b', text_lower):
        suggested.append('scriptural-authority')

    if re.search(r'\bexperience\b', text_lower):
        suggested.append('experience')

    if re.search(r'\brepent', text_lower):
        suggested.append('repentance')

    if re.search(r'\btrin', text_lower):
        suggested.append('trinity')

    if re.search(r'\bchrist', text_lower):
        suggested.append('christology')

    if re.search(r'\bholy\s+ghost\b|holy\s+spirit\b', text_lower):
        suggested.append('pneumatology')

    if re.search(r'\buniversal.*redemp|redemp.*all\b', text_lower):
        suggested.append('universal-redemption')

    if re.search(r'\bkingdom\b.*\bgod\b|reign\b', text_lower):
        suggested.append('reign-of-god')

    if re.search(r'\bprimitive|apostolic', text_lower):
        suggested.append('primitive-christianity')

    return list(set(suggested))

def get_better_theme_for_passage(text, current_themes):
    """Get a better theme if current themes are problematic."""
    keywords = extract_keywords(text)
    suggested = suggest_themes_from_content(text)

    if suggested:
        return suggested[0]

    # Fallback based on keywords
    if 'grace' in keywords:
        return 'justifying-grace'
    if 'christ' in keywords or 'jesus' in keywords:
        return 'christology'
    if 'faith' in keywords:
        return 'justifying-grace'
    if 'holiness' in keywords:
        return 'sanctifying-grace'
    if 'scripture' in keywords:
        return 'scriptural-authority'

    # Ultimate fallback
    return 'experience'

def check_source_title_consistency(source_title, themes, text):
    """Check if themes are consistent with source title."""
    issues = []
    title_lower = source_title.lower()

    # Check specific sermon titles
    if 'trinity' in title_lower and 'trinity' not in themes:
        issues.append({
            'type': 'source-title-mismatch',
            'expected': 'trinity',
            'reason': f'Sermon title "{source_title}" suggests trinity theme'
        })

    if 'christology' in title_lower and 'christology' not in themes:
        issues.append({
            'type': 'source-title-mismatch',
            'expected': 'christology',
            'reason': f'Sermon title "{source_title}" suggests christology theme'
        })

    if 'spirit' in title_lower and 'pneumatology' not in themes:
        # But check if it's actually about Holy Spirit or just generic "spirit"
        if has_pneumatology_content(text):
            issues.append({
                'type': 'source-title-mismatch',
                'expected': 'pneumatology',
                'reason': f'Sermon title "{source_title}" and content suggest pneumatology theme'
            })

    return issues

def main():
    # Configuration
    passages_file = Path('/Users/wilsonpruitt/Documents/Personal/wesley-corpus/chunked/passages.jsonl')
    output_file = passages_file
    report_file = Path('/Users/wilsonpruitt/Documents/Personal/wesley-corpus/metadata/theme-review-report.txt')

    # Load all passages
    passages = []
    with open(passages_file, 'r') as f:
        for line in f:
            passages.append(json.loads(line.strip()))

    print(f"Loaded {len(passages)} passages")
    print("Performing quality review...")

    # Track corrections
    corrections = defaultdict(list)
    removed_themes = defaultdict(int)
    added_themes = defaultdict(int)
    total_issues = 0
    passages_corrected = 0

    # Review each passage
    modified_passages = []
    for passage in passages:
        original_themes = passage.get('themes', [])
        new_themes = original_themes.copy()
        passage_issues = []

        # Check content match with themes
        content_issues = content_match_themes(passage['text'], original_themes)

        # Check source title consistency
        source_title = passage.get('source_title', '')
        title_issues = check_source_title_consistency(source_title, original_themes, passage['text'])

        all_issues = content_issues + title_issues

        if all_issues:
            total_issues += len(all_issues)

            # Process issues and fix themes
            for issue in all_issues:
                if issue['type'] == 'over-tagged':
                    theme_to_remove = issue['theme']
                    if theme_to_remove in new_themes:
                        new_themes.remove(theme_to_remove)
                        removed_themes[theme_to_remove] += 1
                        passage_issues.append(f"Removed {theme_to_remove}: {issue['reason']}")

            # If no themes left, assign a better one
            if not new_themes:
                better_theme = get_better_theme_for_passage(passage['text'], original_themes)
                new_themes.append(better_theme)
                added_themes[better_theme] += 1
                passage_issues.append(f"Added {better_theme}: No themes remained after removal")

        # Update passage if themes changed
        if new_themes != original_themes:
            passage['themes'] = new_themes
            passages_corrected += 1
            corrections[passage['id']] = {
                'original_themes': original_themes,
                'new_themes': new_themes,
                'issues': passage_issues,
                'source_title': source_title
            }

        modified_passages.append(passage)

    # Write corrected passages back
    with open(output_file, 'w') as f:
        for passage in modified_passages:
            f.write(json.dumps(passage) + '\n')

    print(f"Updated {passages_corrected} passages")

    # Generate report
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("WESLEY CORPUS THEME REVIEW REPORT")
    report_lines.append("=" * 80)
    report_lines.append("")
    report_lines.append(f"Passages Reviewed: {len(passages)}")
    report_lines.append(f"Passages Corrected: {passages_corrected}")
    report_lines.append(f"Total Issues Found: {total_issues}")
    report_lines.append("")
    report_lines.append("-" * 80)
    report_lines.append("SUMMARY OF CORRECTIONS BY TYPE")
    report_lines.append("-" * 80)
    report_lines.append("")
    report_lines.append("Themes Removed (Over-tagged):")
    for theme, count in sorted(removed_themes.items(), key=lambda x: -x[1]):
        report_lines.append(f"  {theme}: {count} occurrences")

    report_lines.append("")
    report_lines.append("Themes Added (When removal left passage empty):")
    for theme, count in sorted(added_themes.items(), key=lambda x: -x[1]):
        report_lines.append(f"  {theme}: {count} occurrences")

    report_lines.append("")
    report_lines.append("-" * 80)
    report_lines.append("EXAMPLES OF CORRECTIONS MADE (First 30)")
    report_lines.append("-" * 80)
    report_lines.append("")

    for i, (passage_id, correction) in enumerate(list(corrections.items())[:30]):
        report_lines.append(f"{i+1}. Passage: {passage_id}")
        report_lines.append(f"   Source: {correction['source_title']}")
        report_lines.append(f"   Original themes: {correction['original_themes']}")
        report_lines.append(f"   New themes: {correction['new_themes']}")
        for issue in correction['issues']:
            report_lines.append(f"   - {issue}")
        report_lines.append("")

    # Write report
    with open(report_file, 'w') as f:
        f.write('\n'.join(report_lines))

    print(f"Report written to {report_file}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Passages reviewed: {len(passages)}")
    print(f"Passages corrected: {passages_corrected}")
    print(f"Total issues found and fixed: {total_issues}")
    print("")
    print("Themes removed (over-tagged):")
    for theme, count in sorted(removed_themes.items(), key=lambda x: -x[1]):
        print(f"  {theme}: {count}")
    print("")
    print("Themes added (when removal left passage empty):")
    for theme, count in sorted(added_themes.items(), key=lambda x: -x[1]):
        print(f"  {theme}: {count}")
    print("")
    print(f"Report saved to: {report_file}")

if __name__ == '__main__':
    main()
