import json

with open("data/raw/MSFT/companyfacts.json") as file:
    company = json.load(file)

revenue_tag = "RevenueFromContractWithCustomerExcludingAssessedTax"
revenue_records = company["facts"]["us-gaap"][revenue_tag]["units"]["USD"]

matches = [
    row for row in revenue_records
    if row.get("start") == "2024-07-01"
    and row.get("end") == "2024-09-30"
    and row.get("form") == "10-Q"
]

if not matches:
    raise SystemExit("No revenue record matched this quarter.")

record = max(matches, key=lambda row: row["filed"])
print("Company:", company["entityName"])
print("Period:", record["start"], "to", record["end"])
print(f"Revenue: ${record['val']:,}")
print("SEC filing ID:", record["accn"])
