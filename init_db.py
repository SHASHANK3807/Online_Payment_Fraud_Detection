from flask import Flask
from models import db
from config import Config
import sqlalchemy

def init_database():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    # Create database if it doesn't exist
    # We need to connect to MySQL server directly first (without db name)
    try:
        # Connect to MySQL server to check/create DB
        from urllib.parse import quote_plus
        encoded_pass = quote_plus(Config.DB_PASSWORD)
        engine_url = f"mysql+pymysql://{Config.DB_USERNAME}:{encoded_pass}@{Config.DB_HOST}"
        engine = sqlalchemy.create_engine(engine_url)
        
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME}"))
            print(f"✅ Database '{Config.DB_NAME}' checked/created.")
            
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        print("💡 Hint: Check your .env file credentials.")
        return

    # Create tables
    with app.app_context():
        try:
            db.create_all()
            
            # Add is_admin column to users if it doesn't exist
            try:
                db.session.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
                db.session.commit()
                print("✅ Added 'is_admin' column to users table.")
            except Exception:
                db.session.rollback()

            # Add receiver column to transactions if it doesn't exist
            try:
                db.session.execute(sqlalchemy.text("ALTER TABLE transactions ADD COLUMN receiver VARCHAR(100)"))
                db.session.commit()
                print("✅ Added 'receiver' column to transactions table.")
            except Exception:
                db.session.rollback()
                
            # Add balance column to users if it doesn't exist
            try:
                db.session.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN balance FLOAT DEFAULT 400000.0"))
                db.session.commit()
                print("✅ Added 'balance' column to users table.")
            except Exception:
                db.session.rollback()

            # --- New Senior Protection Columns ---
            try:
                db.session.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN age INT"))
                db.session.commit()
                print("✅ Added 'age' column to users table.")
            except Exception:
                db.session.rollback()
                
            try:
                db.session.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN trusted_contact VARCHAR(120)"))
                db.session.commit()
                print("✅ Added 'trusted_contact' column to users table.")
            except Exception:
                db.session.rollback()

            try:
                db.session.execute(sqlalchemy.text("ALTER TABLE transactions ADD COLUMN requires_cosigner BOOLEAN DEFAULT FALSE"))
                db.session.commit()
                print("✅ Added 'requires_cosigner' column to transactions table.")
            except Exception:
                db.session.rollback()
                
            try:
                db.session.execute(sqlalchemy.text("ALTER TABLE transactions ADD COLUMN cosigner_approved BOOLEAN DEFAULT FALSE"))
                db.session.commit()
                print("✅ Added 'cosigner_approved' column to transactions table.")
            except Exception:
                db.session.rollback()

            try:
                db.session.execute(sqlalchemy.text("ALTER TABLE transactions ADD COLUMN cosigner_token VARCHAR(64)"))
                db.session.commit()
                print("✅ Added 'cosigner_token' column to transactions table.")
            except Exception:
                db.session.rollback()

            try:
                db.session.execute(sqlalchemy.text("ALTER TABLE transactions ADD COLUMN cosigner_otp VARCHAR(4)"))
                db.session.commit()
                print("✅ Added 'cosigner_otp' column to transactions table.")
            except Exception:
                db.session.rollback()

            try:
                db.session.execute(sqlalchemy.text("ALTER TABLE users ADD COLUMN upi_id VARCHAR(100) UNIQUE"))
                db.session.commit()
                print("✅ Added 'upi_id' column to users table.")
            except Exception:
                db.session.rollback()

            # Backfill existing users without UPI ID
            try:
                from models import User
                import re
                users_without_upi = User.query.filter(User.upi_id.is_(None)).all()
                if users_without_upi:
                    for u in users_without_upi:
                        slug = re.sub(r'[^a-z0-9_]', '', u.username.lower())
                        upi_id = f"{slug}@fraudguard"
                        counter = 1
                        while User.query.filter_by(upi_id=upi_id).first() or any(x.upi_id == upi_id for x in users_without_upi if x != u):
                            upi_id = f"{slug}{counter}@fraudguard"
                            counter += 1
                        u.upi_id = upi_id
                    db.session.commit()
                    print(f"✅ Auto-generated UPI IDs for {len(users_without_upi)} existing users.")
            except Exception as e:
                print(f"❌ Error during UPI ID backfill: {e}")
                db.session.rollback()

            # Create default admin user if not exists
            from models import User
            admin_user = User.query.filter_by(email='admin@fraudguard.com').first()
            if not admin_user:
                admin_user = User(username='admin', email='admin@fraudguard.com', is_admin=True)
                admin_user.set_password('admin123')
                db.session.add(admin_user)
                db.session.commit()
                print("👤 Default Admin User Created: admin@fraudguard.com / admin123")
            
            print("✅ Database ready")
        except Exception as e:
            print(f"❌ Error during database setup: {e}")
            db.session.rollback()


if __name__ == "__main__":
    init_database()
