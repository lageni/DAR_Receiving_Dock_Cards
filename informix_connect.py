"""Informix database connection module using pyodbc"""
import os
import pyodbc
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).parent / ".env")


class InformixConnection:
    """Manage Informix database connections"""
    
    def __init__(self):
        self.host = os.getenv("INFORMIX_HOST")
        self.server = os.getenv("INFORMIX_SERVER")
        self.port = os.getenv("INFORMIX_PORT")
        self.user = os.getenv("INFORMIX_USER")
        self.password = os.getenv("INFORMIX_PASSWORD")
        self.database = os.getenv("INFORMIX_DATABASE")
        self.conn = None
    
    def connect(self):
        """Establish connection to Informix"""
        try:
            # Informix connection string for pyodbc
            # Format: DRIVER={driver};SERVER=server;HOST=host;PORT=port;DATABASE=db;USER=user;PASSWORD=pwd;
            conn_str = (
                f"DRIVER={{IBM INFORMIX ODBC DRIVER}};"
                f"SERVER={self.server};"
                f"HOST={self.host};"
                f"PORT={self.port};"
                f"DATABASE={self.database};"
                f"USER={self.user};"
                f"PASSWORD={self.password};"
            )
            
            print(f"[INFO] Connecting to Informix: {self.host}:{self.port}/{self.database}")
            self.conn = pyodbc.connect(conn_str, autocommit=True)
            print("[SUCCESS] Connected to Informix!")
            return self.conn
        
        except Exception as e:
            print(f"[ERROR] Informix connection failed: {str(e)}")
            raise
    
    def disconnect(self):
        """Close connection"""
        if self.conn:
            self.conn.close()
            print("[INFO] Informix connection closed")
    
    def execute_query(self, sql: str):
        """Execute SELECT query and return results"""
        if not self.conn:
            self.connect()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
            
            # Fetch column names
            columns = [desc[0] for desc in cursor.description]
            
            # Fetch all rows
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            results = []
            for row in rows:
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            return results
        
        except Exception as e:
            print(f"[ERROR] Query execution failed: {str(e)}")
            raise
    
    def execute_update(self, sql: str, params=None):
        """Execute INSERT/UPDATE/DELETE and return affected rows"""
        if not self.conn:
            self.connect()
        
        try:
            cursor = self.conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            affected = cursor.rowcount
            cursor.close()
            
            return affected
        
        except Exception as e:
            print(f"[ERROR] Update execution failed: {str(e)}")
            raise


def get_informix_conn():
    """Get a global Informix connection instance"""
    global _informix_conn
    if '_informix_conn' not in globals():
        _informix_conn = InformixConnection()
        _informix_conn.connect()
    return _informix_conn


# Test function
if __name__ == "__main__":
    print("\n=== Testing Informix Connection ===\n")
    
    try:
        conn = InformixConnection()
        conn.connect()
        
        # Test query
        print("[TEST] Running test query...")
        result = conn.execute_query("SELECT COUNT(*) as cnt FROM informix.syscolumns")
        print(f"[SUCCESS] Result: {result}")
        
        conn.disconnect()
        print("\n=== ALL TESTS PASSED ===\n")
    
    except Exception as e:
        print(f"\n[FAILED] {str(e)}\n")
