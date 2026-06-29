#!/usr/bin/env python3
"""Test Informix connection"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load env vars
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# Test if ibm_db is installed
try:
    import ibm_db
    print(" ibm_db is installed")
except ImportError:
    print(" ibm_db NOT installed - installing...")
    import subprocess
    subprocess.check_call(["pip", "install", "ibm-db"])
    import ibm_db
    print(" ibm_db installed successfully")

# Get credentials
host = os.getenv("INFORMIX_HOST")
server = os.getenv("INFORMIX_SERVER")
port = os.getenv("INFORMIX_PORT")
user = os.getenv("INFORMIX_USER")
password = os.getenv("INFORMIX_PASSWORD")
database = os.getenv("INFORMIX_DATABASE")

print(f"\n[INFO] Connecting to Informix:")
print(f"  Host: {host}")
print(f"  Server: {server}")
print(f"  Port: {port}")
print(f"  User: {user}")
print(f"  Database: {database}")

# Build connection string
conn_str = f"SERVER={server};HOST={host};PORT={port};DATABASE={database};USER={user};PASSWORD={password};"

try:
    print(f"\n[CONNECTING]...")
    conn = ibm_db.connect(conn_str, "", "")
    print(" Connection successful!")
    
    # Test a simple query
    print("\n[TESTING] Running test query...")
    sql = "SELECT COUNT(*) as cnt FROM informix.systables"
    stmt = ibm_db.exec_immediate(conn, sql)
    row = ibm_db.fetch_tuple(stmt)
    print(f" Query successful! Result: {row}")
    
    ibm_db.close(conn)
    print("\n ALL TESTS PASSED - Informix connection is working!")
    
except Exception as e:
    print(f" Connection failed: {str(e)}")
    print(f"\n[ERROR] Full traceback:")
    import traceback
    traceback.print_exc()
