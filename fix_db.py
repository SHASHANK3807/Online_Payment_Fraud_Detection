from flask import Flask
from models import db
from config import Config
from sqlalchemy import text

def fix_database():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    with app.app_context():
        # Drop the users table if it exists
        # This forces a recreation with the correct columns
        try:
            print("🔧 Attempting to fix 'users' table...")
            with db.engine.connect() as conn:
                # Disable FK checks to allow dropping referenced tables
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                
                # Drop tables
                conn.execute(text("DROP TABLE IF EXISTS users")) 
                conn.execute(text("DROP TABLE IF EXISTS transactions")) 
                
                # Re-enable FK checks
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                conn.commit()
            print("✅ Dropped old tables.")
            
            # Recreate tables
            db.create_all()
            print("✅ Recreated tables with correct schema.")
            print("🚀 You can now Register and Login successfully.")
            
        except Exception as e:
            print(f"❌ Error fixing database: {e}")

if __name__ == "__main__":
    fix_database()
