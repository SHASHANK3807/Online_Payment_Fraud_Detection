from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    security_question = db.Column(db.String(256))
    security_answer = db.Column(db.String(256)) # Hashed
    balance = db.Column(db.Float, default=400000.0)
    upi_id = db.Column(db.String(100), unique=True, nullable=True)  # e.g. username@fraudguard
    
    # Senior Protection Features
    age = db.Column(db.Integer, nullable=True)
    trusted_contact = db.Column(db.String(120), nullable=True) # Required if age >= 60
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    txn_id = db.Column(db.String(20), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # input features
    amount = db.Column(db.Float, nullable=False)
    device = db.Column(db.String(50))
    location = db.Column(db.String(120))
    merchant = db.Column(db.String(50))

    
    # transacting party details
    email = db.Column(db.String(120)) # sender email
    receiver = db.Column(db.String(120)) # receiver upi/email

    
    # prediction results
    prediction = db.Column(db.String(100)) # "Fraudulent" or "Legitimate" (increased)
    risk_level = db.Column(db.String(100)) # "HIGH", "MEDIUM", "LOW" (increased)

    fraud_probability = db.Column(db.Float)
    
    # verification fields
    otp_code = db.Column(db.String(4))
    is_verified = db.Column(db.Boolean, default=False)

    # Co-signer protection for seniors
    requires_cosigner = db.Column(db.Boolean, default=False)
    cosigner_approved = db.Column(db.Boolean, default=False)
    cosigner_token = db.Column(db.String(64), nullable=True)
    cosigner_otp = db.Column(db.String(4), nullable=True)
    
    def __repr__(self):
        return f'<Transaction {self.txn_id} - {self.risk_level}>'
