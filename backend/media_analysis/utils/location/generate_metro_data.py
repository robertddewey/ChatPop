#!/usr/bin/env python3
"""
Generate metro area JSON mapping from Census Bureau CBSA-FIPS crosswalk data.

This script processes the NBER CBSA-FIPS crosswalk CSV and generates:
1. county_to_metro.json - Maps county+state to CSA (Combined Statistical Area)

Data source: https://data.nber.org/cbsa-csa-fips-county-crosswalk/2023/cbsa2fipsxw_2023.csv
"""

import csv
import json
import re
from pathlib import Path

# Friendly name mappings for major metro areas
# Format: "Official CSA Name" -> "Friendly Name"
FRIENDLY_NAMES = {
    # Major US metros
    "Detroit-Warren-Ann Arbor, MI": "Metro Detroit",
    "New York-Newark-Bridgeport, NY-NJ-CT-PA": "Greater New York",
    "Los Angeles-Long Beach, CA": "Greater Los Angeles",
    "Chicago-Naperville, IL-IN-WI": "Greater Chicago",
    "Washington-Baltimore-Arlington, DC-MD-VA-WV-PA": "Greater Washington DC",
    "San Jose-San Francisco-Oakland, CA": "San Francisco Bay Area",
    "Boston-Worcester-Providence, MA-RI-NH-CT": "Greater Boston",
    "Philadelphia-Camden-Wilmington, PA-NJ-DE-MD": "Greater Philadelphia",
    "Dallas-Fort Worth, TX": "DFW Metroplex",
    "Houston-The Woodlands, TX": "Greater Houston",
    "Miami-Port St. Lucie-Fort Lauderdale, FL": "South Florida",
    "Atlanta--Athens-Clarke County--Sandy Springs, GA-AL": "Metro Atlanta",
    "Phoenix-Mesa, AZ": "Greater Phoenix",
    "Seattle-Tacoma, WA": "Greater Seattle",
    "Minneapolis-St. Paul, MN-WI": "Twin Cities",
    "Denver-Aurora, CO": "Front Range",
    "San Diego-Carlsbad-Tijuana, CA-Baja California (Mex)": "Greater San Diego",
    "Tampa-St. Petersburg-Clearwater, FL": "Tampa Bay",
    "St. Louis-St. Charles-Farmington, MO-IL": "Greater St. Louis",
    "Portland-Vancouver-Salem, OR-WA": "Greater Portland",
    "Pittsburgh-New Castle-Weirton, PA-OH-WV": "Greater Pittsburgh",
    "Charlotte-Concord, NC-SC": "Greater Charlotte",
    "Indianapolis-Carmel-Muncie, IN": "Greater Indianapolis",
    "Las Vegas-Henderson, NV": "Greater Las Vegas",
    "Austin-Round Rock-Georgetown, TX": "Greater Austin",
    "Nashville-Davidson--Murfreesboro, TN": "Greater Nashville",
    "San Antonio-New Braunfels-Pearsall, TX": "Greater San Antonio",
    "Columbus-Marion-Zanesville, OH": "Greater Columbus",
    "Orlando-Lakeland-Deltona, FL": "Greater Orlando",
    "Cleveland-Akron-Canton, OH": "Greater Cleveland",
    "Kansas City-Overland Park-Kansas City, MO-KS": "Greater Kansas City",
    "Salt Lake City-Provo-Ogden, UT": "Wasatch Front",
    "Milwaukee-Racine-Waukesha, WI": "Greater Milwaukee",
    "Cincinnati-Wilmington-Maysville, OH-KY-IN": "Greater Cincinnati",
    "Raleigh-Durham-Cary, NC": "Research Triangle",
    "Jacksonville-St. Marys-Palatka, FL-GA": "Greater Jacksonville",
    "Hartford-East Hartford, CT": "Greater Hartford",
    "New Orleans-Metairie-Hammond, LA-MS": "Greater New Orleans",
    "Buffalo-Cheektowaga-Olean, NY": "Greater Buffalo",
    "Louisville/Jefferson County--Elizabethtown--Bardstown, KY-IN": "Greater Louisville",
    "Rochester-Batavia-Seneca Falls, NY": "Greater Rochester",
    "Greensboro--Winston-Salem--High Point, NC": "Piedmont Triad",
    "Richmond-Connersville, VA": "Greater Richmond",
}


def normalize_county_name(name: str) -> str:
    """Normalize county name for consistent lookups."""
    # Remove common suffixes
    name = re.sub(r'\s+(County|Parish|Borough|Municipality|Census Area|City and Borough)$', '', name, flags=re.IGNORECASE)
    return name.strip().lower()


def get_friendly_name(csa_title: str) -> str:
    """Get friendly name for CSA, or generate one if not in mapping."""
    if csa_title in FRIENDLY_NAMES:
        return FRIENDLY_NAMES[csa_title]

    # Generate a friendly name from the CSA title
    # Take the first city before any hyphen or comma
    match = re.match(r'^([^,-]+)', csa_title)
    if match:
        primary_city = match.group(1).strip()
        return f"Greater {primary_city}"

    return csa_title


def main():
    script_dir = Path(__file__).parent
    csv_path = script_dir / "cbsa2fips_2023.csv"
    output_path = script_dir / "county_to_metro.json"

    if not csv_path.exists():
        print(f"ERROR: CSV file not found at {csv_path}")
        print("Download from: https://data.nber.org/cbsa-csa-fips-county-crosswalk/2023/cbsa2fipsxw_2023.csv")
        return

    # Build county to metro mapping
    # Key: "county_name|state_name" (normalized)
    # Value: {"csa": "Official Name", "friendly": "Friendly Name"}
    county_to_metro = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            csa_title = row.get('csatitle', '').strip()
            county = row.get('countycountyequivalent', '').strip()
            state = row.get('statename', '').strip()

            # Skip if no CSA (not part of a combined statistical area)
            if not csa_title or not county or not state:
                continue

            # Create lookup key
            normalized_county = normalize_county_name(county)
            key = f"{normalized_county}|{state.lower()}"

            # Get friendly name
            friendly = get_friendly_name(csa_title)

            county_to_metro[key] = {
                "csa": csa_title,
                "friendly": friendly,
            }

    # Also create a mapping with full county name for fallback
    # (in case Google returns "Oakland County" instead of just "Oakland")
    additional_mappings = {}
    for key, value in county_to_metro.items():
        county_part, state_part = key.split('|')
        # Add version with "county" suffix
        additional_mappings[f"{county_part} county|{state_part}"] = value

    county_to_metro.update(additional_mappings)

    # Save to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(county_to_metro, f, indent=2, ensure_ascii=False)

    print(f"Generated {output_path}")
    print(f"Total mappings: {len(county_to_metro)}")

    # Print some example mappings
    print("\nExample mappings:")
    examples = [
        "oakland|michigan",
        "wayne|michigan",
        "cook|illinois",
        "los angeles|california",
        "king|washington",
    ]
    for key in examples:
        if key in county_to_metro:
            print(f"  {key} -> {county_to_metro[key]['friendly']}")


if __name__ == "__main__":
    main()
