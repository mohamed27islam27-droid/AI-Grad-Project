from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "12345678" # Make sure this matches your new machine's password

try:
    with GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD)) as driver:
        driver.verify_connectivity()
    print("✅ Connection Successful!")
except Exception as e:
    print(f"❌ Connection Failed: {e}")