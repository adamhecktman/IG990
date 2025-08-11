#!/usr/bin/env python3
"""
extract_990_grants_xml.py

Usage:
  python extract_990_grants_xml.py --xml bank_of_america_990.xml --out grants.csv [--debug]

Requires: lxml, pandas
  pip install lxml pandas
"""

import argparse
import re
from lxml import etree as ET
import pandas as pd
import sys

# candidate element local-names to try for recipient name and amount
NAME_TAG_CANDIDATES = [
    "BusinessNameLine1Txt",
    "BusinessNameLine1",
    "BusinessName",
    "RecipientBusinessName"
]

AMOUNT_TAG_CANDIDATES = [
    "Amt",
    "Amount",
    "GrantAmount",
    "ContributionAmt",
    "ContributionAmount"
]

AMOUNT_CLEAN_RE = re.compile(r"[^0-9\.\-]")

def first_text_for_tags(node, tag_names):
    """Return the first non-empty text found for any of the tag_names inside node (namespace-agnostic)."""
    for tag in tag_names:
        elems = node.xpath(".//*[local-name() = $t]", t=tag)
        for e in elems:
            text = ''.join(e.itertext()).strip()
            if text:
                return text
    return None

def clean_amount_to_float(s):
    if s is None:
        return None
    s = s.strip()
    s = s.replace("\xa0", "")  # NBSP
    s = s.replace(",", "")
    # Allow parentheses as negative
    s = s.replace("(", "-").replace(")", "")
    s2 = AMOUNT_CLEAN_RE.sub("", s)
    if s2 == "":
        return None
    try:
        return float(s2)
    except ValueError:
        return None

def extract_grants(xml_path, debug=False):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # find all grant groups (namespace-agnostic)
    grant_nodes = root.xpath("//*[local-name() = 'GrantOrContributionPdDurYrGrp']")
    if not grant_nodes and debug:
        # fallback: find anything with 'grant' in its local name (rare)
        grant_nodes = root.xpath("//*[contains(translate(local-name(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'grant')]")

    if debug:
        print(f"[DEBUG] Found {len(grant_nodes)} grant-like nodes")

    results = []
    for node in grant_nodes:
        name = first_text_for_tags(node, NAME_TAG_CANDIDATES)
        amount_raw = first_text_for_tags(node, AMOUNT_TAG_CANDIDATES)
        if not name or not amount_raw:
            if debug:
                ln = ET.QName(node).localname
                print(f"[DEBUG] skipping node ({ln}) — name found: {bool(name)}, amount found: {bool(amount_raw)}")
            continue
        amt_val = clean_amount_to_float(amount_raw)
        if amt_val is None:
            if debug:
                print(f"[DEBUG] couldn't parse amount: {amount_raw!r} for name: {name!r}")
            continue
        # skip totals (some filings include a Total row inside grant sections)
        if "total" in name.lower():
            continue
        results.append({"recipient": name, "amount": amt_val})
    return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", "-x", required=True, help="Path to 990 XML file")
    ap.add_argument("--out", "-o", required=True, help="Output CSV path")
    ap.add_argument("--debug", action="store_true", help="Print debug info")
    args = ap.parse_args()

    rows = extract_grants(args.xml, debug=args.debug)
    if not rows:
        print("No grants extracted (0 rows). Use --debug to see diagnostics.", file=sys.stderr)
        if args.debug:
            print("Try printing a small XML snippet around a GrantOrContributionPdDurYrGrp and paste here for adjustments.")
        sys.exit(1)

    df = pd.DataFrame(rows, columns=["recipient", "amount"])
    df.to_csv(args.out, index=False)
    print(f"Saved {len(df)} rows to {args.out}")

if __name__ == "__main__":
    main()
