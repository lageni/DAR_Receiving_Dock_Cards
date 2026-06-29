"""Test Informix query: select * from rdc_db:informix.po_line limit 10"""
from informix_connect import InformixConnection

print("\n=== Testing Informix Query ===\n")

try:
    conn = InformixConnection()
    conn.connect()
    
    # Test query from user
    sql = "SELECT * FROM rdc_db:informix.po_line LIMIT 10"
    
    print(f"[QUERY] {sql}\n")
    results = conn.execute_query(sql)
    
    print(f"[SUCCESS] Retrieved {len(results)} rows\n")
    
    if results:
        # Print column names
        print("Columns:", list(results[0].keys()))
        print("\nFirst row:")
        for key, val in results[0].items():
            print(f"  {key}: {val}")
        
        if len(results) > 1:
            print(f"\n... and {len(results)-1} more rows")
    
    conn.disconnect()
    print("\n=== TEST PASSED ===\n")
    
except Exception as e:
    print(f"\n[FAILED] {str(e)}\n")
