from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import secrets


import re
import random
import time
import pickle
import numpy as np
import warnings
from datetime import datetime, timedelta
from validators import TransactionValidator
from models import db, Transaction, User
from config import Config

warnings.filterwarnings('ignore')

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Database
db.init_app(app)

# Initialize Mail
mail = Mail(app)


# Configure session to end when browser closes (but persist during browsing)
app.config['SESSION_PERMANENT'] = False

# Initialize Login Manager
login = LoginManager(app)
login.login_view = 'login'
login.login_message = ""  # Disable default "Please log in to access this page." warnings

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

# Global variables for model and scaler
model = None
scaler = None
feature_names = None

def load_model():
    """Load trained ML model and scaler."""
    global model, scaler, feature_names
    
    try:
        with open('fraud_model.pkl', 'rb') as f:
            model = pickle.load(f)
        with open('fraud_scaler.pkl', 'rb') as f:
            scaler = pickle.load(f)
        with open('fraud_features.pkl', 'rb') as f:
            feature_names = pickle.load(f)
        print("✅ Model loaded successfully")
        return True
    except FileNotFoundError:
        print("⚠️  Model files not found. Please run: python train_model.py")
        return False

def encode_feature(value, feature_name, feature_mapping=None):
    """Encode categorical features to numeric values."""
    
    encoding_map = {
        'device': {'mobile': 1, 'web': 2, 'tablet': 3},
        'location': {
            'mumbai': 1, 'delhi': 2, 'bangalore': 3, 'hyderabad': 4, 
            'chennai': 5, 'kolkata': 6, 'pune': 7, 'ahmedabad': 8, 'other': 9
        },
        'merchant': {
            'retail': 1, 'food': 2, 'travel': 3, 'entertainment': 4, 
            'utilities': 5, 'healthcare': 6, 'education': 7, 'other': 8
        }

    }
    
    if feature_name in encoding_map:
        # If value not found, default to 'other' index if it exists, else 0
        return encoding_map[feature_name].get(value, encoding_map[feature_name].get('other', 0))

    return value

def predict_fraud(transaction_data):
    """
    Predict if transaction is fraudulent using ML model.
    
    Args:
        transaction_data: dict with keys matching feature_names
    
    Returns:
        dict with prediction, confidence, and risk level
    """
    
    if model is None or scaler is None:
        return {
            'error': True,
            'message': 'Model not loaded. Run train_model.py first.',
            'result': 'verify'
        }
    
    try:
        # Prepare feature vector in correct order
        X = np.array([[transaction_data.get(feat, 0) for feat in feature_names]])
        
        # Scale features
        X_scaled = scaler.transform(X)
        
        # Get prediction and probability
        prediction = model.predict(X_scaled)[0]
        probability = model.predict_proba(X_scaled)[0]
        
        fraud_probability = probability[1]  # Probability of fraud
        legitimate_probability = probability[0]  # Probability of legitimate
        
        # Determine risk level
        if fraud_probability >= 0.7:
            result = "fraud"
            risk_level = "🔴 HIGH RISK"
        elif fraud_probability >= 0.4:
            result = "verify"
            risk_level = "🟡 MEDIUM RISK"
        else:
            result = "success"
            risk_level = "🟢 LOW RISK"
        
        return {
            'error': False,
            'result': result,
            'fraud_probability': round(fraud_probability * 100, 2),
            'legitimate_probability': round(legitimate_probability * 100, 2),
            'risk_level': risk_level,
            'prediction': 'Fraudulent' if prediction == 1 else 'Legitimate'
        }
    
    except Exception as e:
        return {
            'error': True,
            'message': f'Prediction error: {str(e)}',
            'result': 'verify'
        }

def extract_time_features(timestamp=None):
    """Extract temporal features from transaction time."""
    if timestamp is None:
        timestamp = datetime.now()
    
    return {
        'hour': timestamp.hour,
        'minute': timestamp.minute,
        'day_of_week': timestamp.weekday(),
        'is_weekend': 1 if timestamp.weekday() >= 5 else 0,
        'is_night': 1 if timestamp.hour < 6 or timestamp.hour >= 22 else 0,
        'is_business_hours': 1 if 9 <= timestamp.hour <= 17 else 0
    }


def get_user_behavior_features(email):
    """Analyze user's transaction patterns from history, including location behavior."""
    
    # Get past transactions (last 30 days) - ONLY LEGITIMATE ONES
    cutoff = datetime.utcnow() - timedelta(days=30)
    past_txns = Transaction.query.filter(
        Transaction.email == email,
        Transaction.timestamp >= cutoff,
        Transaction.prediction == 'Legitimate'
    ).order_by(Transaction.timestamp.desc()).all()
    
    if len(past_txns) == 0:
        return {
            'avg_amount': 0,
            'std_amount': 0,
            'txn_count': 0,
            'is_new_user': 1,
            'usual_hours': [],
            'usual_devices': [],
            'usual_locations': [],
            'location_change_count': 0,
            'last_txn_time': None,
            'recent_burst_count': 0,
            'recent_total_amount': 0
        }

    
    amounts = [t.amount for t in past_txns]
    hours = [t.timestamp.hour for t in past_txns]
    devices = [t.device for t in past_txns]
    locations = [t.location for t in past_txns]
    
    # Calculate location changes (how often they switch cities)
    location_changes = 0
    for i in range(len(locations) - 1):
        if locations[i] != locations[i+1]:
            location_changes += 1
            
    # Calculate Velocity Features
    last_txn_time = past_txns[0].timestamp if past_txns else None
    
    # Count transactions and total amount in the last hour (for burst detection)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_txns = [t for t in past_txns if t.timestamp >= one_hour_ago]
    recent_burst_count = len(recent_txns)
    recent_total_amount = sum(t.amount for t in recent_txns)
    
    return {
        'avg_amount': float(np.mean(amounts)) if amounts else 0,
        'std_amount': float(np.std(amounts)) if len(amounts) > 1 else 0,
        'txn_count': len(past_txns),
        'is_new_user': 0 if len(past_txns) > 0 else 1,

        'usual_hours': hours,
        'usual_devices': list(set(devices)),
        'usual_locations': list(set(locations)), # All locations used recently
        'location_change_count': location_changes,
        'last_txn_time': last_txn_time,
        'recent_burst_count': recent_burst_count,
        'recent_total_amount': recent_total_amount
    }


def get_receiver_reputation(receiver_email):
    """Analyze global history to check if a receiver is flagged for fraud based on fraud rate."""
    if not receiver_email:
        return {'is_flagged': False, 'fraud_count': 0, 'total_count': 0, 'fraud_rate': 0}
        
    # Get total transaction counts for this receiver
    total_count = Transaction.query.filter_by(receiver=receiver_email).count()
    if total_count == 0:
        return {'is_flagged': False, 'fraud_count': 0, 'total_count': 0, 'fraud_rate': 0}
        
    # Count how many times this receiver has been associated with Fraudulent transactions
    fraud_count = Transaction.query.filter_by(
        receiver=receiver_email,
        prediction='Fraudulent'
    ).count()
    
    fraud_rate = (fraud_count / total_count) * 100
    
    # Flag if fraud rate is high (>= 25%) AND they have enough history (>= 2 txns)
    # This prevents flagging someone with just 1 blocked txn (100% rate)
    is_flagged = (fraud_rate >= 25 and total_count >= 2) or (fraud_count >= 3)
    
    return {
        'is_flagged': is_flagged,
        'fraud_count': fraud_count,
        'total_count': total_count,
        'fraud_rate': round(fraud_rate, 2)
    }

def resolve_receiver_upi(upi_id):
    """
    Resolve a FraudGuard UPI ID to the registered user's email if they exist.
    For unknown/external UPI IDs, returns the UPI ID itself as the identifier.
    Returns: (user_obj or None, identifier_string)
    """
    if not upi_id:
        return None, ''
    upi_id = upi_id.strip().lower()
    user = User.query.filter_by(upi_id=upi_id).first()
    if user:
        return user, user.email
    return None, upi_id  # External / unknown — use UPI ID as identifier


@app.route('/api/check-receiver', methods=['POST'])
@login_required
def check_receiver():
    """API endpoint for frontend to check receiver's details and reputation before paying."""
    data = request.get_json()
    receiver_upi = data.get('receiver', '').lower()
    
    # Check if receiver is a registered FraudGuard user
    user, identifier = resolve_receiver_upi(receiver_upi)
    
    reputation = get_receiver_reputation(identifier)
    
    # Add registration info to the response
    reputation.update({
        'is_registered': user is not None,
        'receiver_username': user.username if user else None,
        'receiver_email': user.email if user else identifier
    })
    
    return jsonify(reputation)

def predict_fraud_enhanced(transaction_data, user_email):
    """Enhanced prediction with transaction history, time analysis, and receiver reputation."""
    
    # 1. Get current time features
    time_features = extract_time_features()
    
    # 2. Get user behavioral features
    behavior = get_user_behavior_features(user_email)
    
    # 3. Get receiver reputation
    receiver_upi = transaction_data.get('receiver', '').lower()
    reputation = get_receiver_reputation(receiver_upi)
    
    # 4. Detect anomalies
    anomalies = []
    risk_boost = 0
    
    # Check receiver reputation (Scam Protection)
    if reputation['is_flagged']:
        anomalies.append(f"⚠️ HIGH RISK: Receiver ({receiver_upi}) has a {reputation['fraud_rate']}% fraud rate ({reputation['fraud_count']}/{reputation['total_count']} transactions)!")
        risk_boost += 0.4 # Significant boost for known bad actors
    elif reputation['fraud_count'] > 0:
        anomalies.append(f"⚠️ WARNING: Receiver has a {reputation['fraud_rate']}% fraud record in their history.")
        risk_boost += 0.2

    
    # Check unusual amount
    raw_amount = transaction_data.get('amount_raw', 0)
    if behavior['avg_amount'] > 0 and raw_amount > 0:
        amount_ratio = raw_amount / behavior['avg_amount']
        if amount_ratio > 3.0:
            anomalies.append(f"💰 CRITICAL: Amount (₹{raw_amount:,.2f}) is {amount_ratio:.1f}x higher than your average spending.")
            risk_boost += 0.2
        elif amount_ratio > 2.0:
            anomalies.append(f"💰 UNUSUAL: Amount is {amount_ratio:.1f}x higher than your typical transaction.")
            risk_boost += 0.1

    
    # Check unusual time
    if time_features['is_night']:
        anomalies.append("🌙 TIME RISK: Transaction initiated during high-risk night hours (12 AM - 6 AM).")
        risk_boost += 0.15

    
    # Check if hour is unusual for this user
    if behavior['usual_hours'] and time_features['hour'] not in behavior['usual_hours']:
        if len(behavior['usual_hours']) >= 3:  # Only if we have enough history
            anomalies.append("🕒 TEMPORAL ANOMALY: This activity is outside your normal transacting hours.")
            risk_boost += 0.1

    
    # Check unusual location
    if behavior['usual_locations'] and transaction_data.get('location') not in behavior['usual_locations']:
        if len(behavior['usual_locations']) >= 2:  # Only if they have a history of multiple locations
            anomalies.append(f"📍 LOCATION RISK: Transaction from a new or unrecognized location ({transaction_data.get('location').capitalize()}).")
            risk_boost += 0.2
        else:
            anomalies.append("🌐 NEW LOCATION: This is the first time you are transacting from this city.")

            risk_boost += 0.1
            
    # Check frequency of location change
    if behavior['location_change_count'] > 3: # Fast switching between locations
        anomalies.append("Frequent location changes detected (high velocity)")
        risk_boost += 0.15

    # Check Transaction Velocity (Time-Gap)
    if behavior['last_txn_time']:
        time_diff = datetime.utcnow() - behavior['last_txn_time']
        minutes_since_last = time_diff.total_seconds() / 60
        
        if minutes_since_last < 1:
            anomalies.append(f"Extreme Velocity: Successive transaction in under 60 seconds (Bot/Script Risk)")
            risk_boost += 0.40
        elif minutes_since_last < 15:
            anomalies.append(f"Recent transaction detected ({int(minutes_since_last)} mins ago) - High Frequency")
            risk_boost += 0.15
            
    # Check for Transaction Burst (3+ in 1 hour)
    if behavior['recent_burst_count'] >= 3:
        anomalies.append(f"Transaction burst detected ({behavior['recent_burst_count']} txns in last hour)")
        risk_boost += 0.25

    # Joint Amount-Time Risk Analysis
    raw_amount = transaction_data.get('amount_raw', 0) # Use un-logged amount for clearer rules
    if time_features['is_night'] and raw_amount > 10000:
        anomalies.append("Dangerous Pattern: High-value transaction during late-night hours")
        risk_boost += 0.3
    
    # Cumulative Spending Limit (Last 1 Hour)
    max_hourly_limit = 25000
    if (behavior['recent_total_amount'] + raw_amount) > max_hourly_limit:
        anomalies.append(f"Cumulative spending limit exceeded (₹{int(behavior['recent_total_amount'] + raw_amount):,} in last hour)")
        risk_boost += 0.35

    # 4. Get base ML prediction

    ml_prediction = predict_fraud(transaction_data)
    
    if ml_prediction.get('error'):
        return ml_prediction
    
    # 6. Generate AI insights based on feature importance
    ai_insights = []
    if hasattr(model, 'feature_importances_') and feature_names:
        # Get feature importances
        importances = model.feature_importances_
        # Get indices of top 3 most important features
        top_indices = np.argsort(importances)[-3:][::-1]
        
        for idx in top_indices:
            feat_name = feature_names[idx]
            importance = importances[idx]
            # Use raw values for insights, not transformed
            if feat_name == 'amount':
                feat_value = transaction_data.get('amount_raw', 0)
            else:
                feat_value = transaction_data.get(feat_name, 0)
            
            # Generate insight based on feature
            if feat_name == 'amount':
                if feat_value > 10000:
                    ai_insights.append(f"💰 Extremely high transaction amount (₹{feat_value:,.0f}) triggered maximum security protocols")
                elif feat_value > 5000:
                    ai_insights.append(f"💰 High-value transaction (₹{feat_value:,.0f}) required enhanced verification")
                elif feat_value > 1000:
                    ai_insights.append(f"💰 Elevated transaction amount (₹{feat_value:,.0f}) contributed to risk assessment")
                else:
                    ai_insights.append(f"💰 Transaction amount analysis completed for ₹{feat_value:,.0f}")
            elif feat_name == 'hours':
                if feat_value >= 22 or feat_value <= 6:
                    ai_insights.append(f"🌙 Late-night transaction timing ({int(feat_value)}:00) activated high-risk monitoring")
                elif feat_value >= 18 or feat_value <= 9:
                    ai_insights.append(f"🕒 Off-peak hours transaction ({int(feat_value)}:00) flagged for additional scrutiny")
                else:
                    ai_insights.append(f"🕒 Business hours transaction ({int(feat_value)}:00) processed normally")
            elif feat_name == 'location_match':
                if feat_value == 0:
                    ai_insights.append(f"📍 Unfamiliar transaction location detected - geographic risk factor identified")
                else:
                    ai_insights.append(f"📍 Location verification successful - known transaction area")
            elif feat_name == 'is_new_merchant':
                if feat_value == 1:
                    ai_insights.append(f"🏪 First-time merchant interaction triggered enhanced security checks")
                else:
                    ai_insights.append(f"🏪 Known merchant relationship verified")
            elif feat_name == 'phone_match':
                if feat_value == 0:
                    ai_insights.append(f"📞 Phone number mismatch detected - identity verification concern")
                else:
                    ai_insights.append(f"📞 Phone verification successful")
            elif feat_name == 'device_type_code':
                ai_insights.append(f"📱 Device fingerprinting analysis completed")
            elif feat_name == 'merchant_category_code':
                ai_insights.append(f"🏪 Merchant category risk assessment performed")
            elif feat_name == 'is_weekend':
                if feat_value == 1:
                    ai_insights.append(f"📅 Weekend transaction pattern analyzed")
                else:
                    ai_insights.append(f"📅 Weekday transaction processed")
            else:
                ai_insights.append(f"🔍 Advanced feature '{feat_name}' analysis completed")
    
    # 5. Adjust risk based on behavioral analysis
    base_prob = ml_prediction['fraud_probability']
    adjusted_fraud_prob = min(base_prob + risk_boost * 100, 100)
    
    # Determine final risk level and final prediction string
    if adjusted_fraud_prob >= 95:
        result = "fraud"
        risk_level = "🔴 CRITICAL RISK"
        final_prediction = "Permanently Blocked"
    elif adjusted_fraud_prob >= 40:
        result = "verify"
        risk_level = "🟡 HIGH RISK"
        final_prediction = "Verification Required"
    else:
        result = "success"
        risk_level = "🟢 LOW RISK"
        final_prediction = "Legitimate"

    
    return {
        **ml_prediction,
        'prediction': final_prediction, # Override base ML prediction
        'fraud_probability': round(adjusted_fraud_prob, 2),
        'legitimate_probability': round(100.0 - adjusted_fraud_prob, 2),
        'base_ml_probability': base_prob,
        'behavioral_boost': round(risk_boost * 100, 2),
        'result': result,
        'risk_level': risk_level,
        'anomalies': anomalies,
        'ai_insights': ai_insights,
        'behavioral_analysis': {
            'user_avg_amount': round(behavior['avg_amount'], 2) if behavior['avg_amount'] > 0 else 0,
            'transaction_count': behavior['txn_count'],
            'is_new_user': behavior['is_new_user']
        },
        'time_analysis': {
            'hour': time_features['hour'],
            'minute': time_features['minute'],
            'is_night': time_features['is_night'],
            'is_weekend': time_features['is_weekend'],
            'is_business_hours': time_features['is_business_hours']
        }

    }


def send_verification_email(email, otp, amount):
    """Helper to send transaction verification emails."""
    try:
        msg = Message(
            subject="🔒 Transaction Verification Code",
            recipients=[email],
            body=f"Hello,\n\nWe detected a highly unusual pattern for your transaction of ₹{amount:,.2f}.\n\nYour 4-digit verification code is: {otp}\n\nIf you did not initiate this transaction, please contact support immediately.\n\nBest regards,\nFraud Detection Team"
        )
        mail.send(msg)
        print(f"✅ OTP email sent to {email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email to {email}: {e}")
        # Always fallback to console for development
        print(f"🔒 [FALLBACK] OTP for {email} is: {otp}")
        return False




@app.route('/')
def index():
    return render_template('intro.html')


@app.route('/intro')
def intro():
    return render_template('intro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if current_user.is_authenticated:
            logout_user() # Log out any existing session if they try to login with new credentials
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user)
        if user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('transaction'))

    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('transaction'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/emergency-options/<txn_id>')
@login_required
def emergency_options(txn_id):
    """Selection screen for seniors to choose emergency verification method."""
    transaction = Transaction.query.filter_by(txn_id=txn_id, email=current_user.email).first()
    if not transaction:
        flash("Transaction not found.")
        return redirect(url_for('history'))
        
    return render_template('emergency_selection.html', txn_id=txn_id)

@app.route('/emergency-dual-otp/<txn_id>')
@login_required
def initiate_emergency_dual_otp(txn_id):
    """Initiate Dual-OTP as an emergency override for seniors."""
    transaction = Transaction.query.filter_by(txn_id=txn_id, email=current_user.email).first()
    if not transaction:
        flash("Transaction not found.")
        return redirect(url_for('history'))
    
    # Update transaction to require co-signer if not already set
    transaction.requires_cosigner = True
    transaction.prediction = 'Pending Dual-OTP (Emergency)'
    db.session.commit()
    
    return start_dual_otp_flow(transaction)

def start_dual_otp_flow(transaction):
    """Helper to generate OTPs, send emails, and redirect to dual-verification page."""
    sender_otp = str(random.randint(1000, 9999))
    trusted_otp = str(random.randint(1000, 9999))
    
    transaction.otp_code = sender_otp
    transaction.cosigner_otp = trusted_otp
    db.session.commit()
    
    # Send Sender OTP
    try:
        msg = Message(
            subject="🔐 Your Transaction OTP - FraudGuard",
            recipients=[transaction.email],
            body=f"Hello {current_user.username},\n\nYour transaction of ₹{transaction.amount:,.2f} to {transaction.receiver} requires dual verification.\n\nYour personal verification code is: {sender_otp}\n\nPlease enter this code along with the code sent to your Trusted Contact to proceed.\n\nFraudGuard Security"
        )
        mail.send(msg)
    except Exception as e:
        print(f"❌ Failed to send sender OTP: {e}")
        print(f"🔒 [FALLBACK] Sender OTP: {sender_otp}")

    # Send Trusted Contact OTP
    try:
        msg = Message(
            subject="⚠️ Action Required: Trusted Approval Code - FraudGuard",
            recipients=[current_user.trusted_contact],
            body=f"Hello,\n\n{current_user.username} is attempting to transfer ₹{transaction.amount:,.2f} to {transaction.receiver}.\n\nAs their Trusted Contact, we require your authorization. Please provide them with the following 4-digit code if you approve of this transfer:\n\nVerification Code: {trusted_otp}\n\nIf you do not recognize this transaction, advise them to cancel immediately.\n\nFraudGuard Security"
        )
        mail.send(msg)
        print(f"✅ Trusted contact OTP sent to {current_user.trusted_contact}")
    except Exception as e:
        print(f"❌ Failed to send trusted OTP: {e}")
        print(f"🔒 [FALLBACK] Trusted OTP: {trusted_otp}")
        
    return render_template('dual_verify_otp.html', 
                           amount=transaction.amount, 
                           receiver=transaction.receiver, 
                           trusted_contact=current_user.trusted_contact, 
                           txn_id=transaction.txn_id)

def finalize_transaction(txn, prediction="Legitimate", risk_level="🟢 LOW RISK"):
    """
    Centralized logic to mark a transaction as completed.
    Balance logic removed — always returns True.
    """
    if txn.is_verified:
        return True  # Already processed

    txn.is_verified = True
    txn.prediction = prediction
    txn.risk_level = risk_level
    db.session.commit()
    return True

@app.route('/verify-challenge/<txn_id>', methods=['GET', 'POST'])
@login_required
def verify_challenge(txn_id):
    """Handle knowledge-based security challenge for emergency overrides."""
    txn = Transaction.query.filter_by(txn_id=txn_id, email=current_user.email).first()
    if not txn:
        flash('Transaction not found')
        return redirect(url_for('transaction'))

    if request.method == 'POST':
        answer = request.form.get('security_answer', '').lower().strip()
        
        # Verify hashed answer
        if check_password_hash(current_user.security_answer, answer):
            # Success!
            # For seniors, if they prove identity with the question, we can finalize (Emergency Override)
            # Adults still do the extra OTP step as per old flow
            if current_user.age and current_user.age >= 60:
                finalize_transaction(txn, prediction="Legitimate (Emergency Override)")
                flash('Identity Verified! Emergency transaction approved.')
                return render_template('result.html',
                                     result='success',
                                     amount=txn.amount,
                                     txn_id=txn_id,
                                     prediction={
                                         'prediction': 'Legitimate (Emergency Override)',
                                         'risk_level': '🟢 LOW RISK',
                                         'fraud_probability': txn.fraud_probability or 0.0,
                                         'legitimate_probability': 100.0 - (txn.fraud_probability or 0.0),
                                         'error': False,
                                         'anomalies': ['✅ Identity verified via emergency security question']
                                     })
            
            # Adult Flow: Security Question + Single OTP
            otp = str(random.randint(1000, 9999))
            txn.otp_code = otp
            db.session.commit()
            
            # Send the email again (to the registered email)
            send_verification_email(current_user.email, otp, txn.amount)
            
            flash('Identity Verified! One final step: Enter the 4-digit code sent to your email.')
            return redirect(url_for('verify_otp', txn_id=txn_id))
        else:
            return render_template('verify_challenge.html', 
                                 question=current_user.security_question,
                                 txn_id=txn_id,
                                 error="❌ Incorrect answer. Please try again.")

    return render_template('verify_challenge.html', 
                          question=current_user.security_question,
                          txn_id=txn_id)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('intro'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        age_str = request.form.get('age')
        trusted_contact = request.form.get('trusted_contact', '').strip()
        password = request.form.get('password')
        q = request.form.get('security_question')
        a = request.form.get('security_answer')
        
        try:
            age = int(age_str)
        except (TypeError, ValueError):
            age = 0
            
        if age < 18:
            flash('You must be at least 18 years old to register')
            return redirect(url_for('register'))
            
        if age >= 60 and not trusted_contact:
            flash('A trusted contact email is required for users 60 and older.')
            return redirect(url_for('register'))
            
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
            
        # Store registration details temporarily in session
        hashed_answer = generate_password_hash(a.lower().strip())
        otp = str(random.randint(1000, 9999))
        
        session['reg_details'] = {
            'username': username,
            'email': email,
            'age': age,
            'trusted_contact': trusted_contact,
            'password': password, # Need to be careful here, ideally hash it now
            'security_question': q,
            'security_answer_hash': hashed_answer,
            'otp': otp
        }
        
        # Send OTP email
        try:
            msg = Message(
                subject="🔒 Verify Your Email - FraudGuard",
                recipients=[email],
                body=f"Hello {username},\n\nWelcome to FraudGuard!\n\nYour 4-digit email verification code is: {otp}\n\nIf you did not request this, please ignore this email.\n\nBest regards,\nFraudGuard Security Team"
            )
            mail.send(msg)
            print(f"✅ Registration OTP email sent to {email}")
        except Exception as e:
            print(f"❌ Failed to send registration email to {email}: {e}")
            print(f"🔒 [FALLBACK] Registration OTP for {email} is: {otp}")
            
        flash('Verification code sent! Please check your email.')
        return redirect(url_for('verify_registration'))
        
    return render_template('register.html')

@app.route('/verify-registration', methods=['GET', 'POST'])
def verify_registration():
    if current_user.is_authenticated:
        return redirect(url_for('intro'))
        
    reg_details = session.get('reg_details')
    if not reg_details:
        flash('Registration session expired. Please start again.')
        return redirect(url_for('register'))
        
    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()
        
        if entered_otp == reg_details['otp']:
            # Success! Create the user in the database
            user = User(
                username=reg_details['username'], 
                email=reg_details['email'], 
                age=reg_details.get('age'),
                trusted_contact=reg_details.get('trusted_contact'),
                security_question=reg_details['security_question']
            )
            user.set_password(reg_details['password'])
            user.security_answer = reg_details['security_answer_hash']

            # Generate a unique FraudGuard UPI ID for this user
            slug = re.sub(r'[^a-z0-9_]', '', reg_details['username'].lower())
            upi_id = f"{slug}@fraudguard"
            counter = 1
            while User.query.filter_by(upi_id=upi_id).first():
                upi_id = f"{slug}{counter}@fraudguard"
                counter += 1
            user.upi_id = upi_id

            db.session.add(user)
            db.session.commit()

            # Clear the session
            session.pop('reg_details', None)

            flash(f'Registration successful! Your FraudGuard UPI ID is: {upi_id} — save this to receive payments. Please login.', "success")
            return redirect(url_for('login'))
        else:
            flash('Incorrect verification code. Please try again.')
            
    return render_template('verify_registration.html', email=reg_details['email'])
@app.route('/transaction')
@login_required
def transaction():
    email = current_user.email
    if '@' in email:
        username, domain = email.split('@')
        if len(username) > 3:
            masked = username[:2] + '***' + username[-1]
        elif len(username) > 1:
            masked = username[0] + '***'
        else:
            masked = '***'
        masked_email = f"{masked}@{domain}"
    else:
        masked_email = email
    return render_template('index.html', masked_email=masked_email)


@app.route('/processing', methods=['POST'])
@login_required
def processing():
    """Validate form data and display processing page while validating in background."""
    
    # Extract form data
    amount = request.form.get('amount', '')
    device = request.form.get('device', 'mobile')
    location = request.form.get('location', 'mumbai').lower()
    merchant = request.form.get('merchant', 'other')
    phone = request.form.get('phone', '')
    receiver_upi = request.form.get('receiver', '')
    receiver_email = request.form.get('receiver_email', '')
    email = current_user.email # Force use of logged-in user's email for security



    
    try:
        amt = float(amount)
    except:
        amt = 0
    
    # ========== LAYER 1: DATA VALIDATION ==========
    validator = TransactionValidator()
    
    transaction_input = {
        'amount': amount,
        'phone': phone,
        'receiver': receiver_upi,  # Validate as UPI ID format
        'email': email,
        'location': location
    }

    # Self-UPI transfer block
    current_user_upi = current_user.upi_id.lower() if current_user.upi_id else ''
    receiver_clean = receiver_upi.strip().lower()
    if current_user_upi and current_user_upi == receiver_clean:
        txn_id = "TXN" + str(random.randint(100000, 999999))
        new_txn = Transaction(
            txn_id=txn_id,
            amount=amt,
            device=device,
            location=location,
            merchant=merchant,
            receiver=receiver_upi,
            email=email,
            prediction='Blocked (Self Transfer)',
            risk_level='🔴 BLOCKED',
            fraud_probability=100.0
        )
        db.session.add(new_txn)
        db.session.commit()
        return render_template('result.html',
                               result='fraud',
                               amount=amt,
                               txn_id=txn_id,
                               prediction={
                                   'result': 'fraud',
                                   'error': False,
                                   'fraud_probability': 100,
                                   'reason': 'Self-UPI transfers are not allowed for security reasons.'
                               },
                               validation_error="❌ Self Transfer Blocked", 
                               validation_details={'self_transfer': True})

    
    is_valid, validation_msg, validation_details = validator.validate_all(transaction_input)
    
    if not is_valid:
        """Input validation failed - show error immediately"""
        txn_id = "TXN" + str(random.randint(100000, 999999))
        
        try:
            new_txn = Transaction(
                txn_id=txn_id,
                amount=amt,
                device=device,
                location=location,
                merchant=merchant,
                receiver=receiver_upi,
                email=email,
                prediction='Blocked (Validation Failed)',
                risk_level='🔴 CRITICAL',
                fraud_probability=100.0
            )
            db.session.add(new_txn)
            db.session.commit()
        except Exception as e:
            print(f"Database Error: {e}")
            
        return render_template('result.html',
                               result='fraud',
                               amount=amt,
                               txn_id=txn_id,
                               prediction={
                                   'result': 'fraud',
                                   'error': False,
                                   'fraud_probability': 100,
                                   'reason': 'Data validation failed'
                               },
                               validation_error=validation_msg,
                               validation_details=validation_details)
                               
    # ========== LAYER 1.5: BEHAVIORAL & AGE-BASED FRICTION ==========
    behavior = get_user_behavior_features(email)
    time_features = extract_time_features()
    
    # Calculate flags locally (they need current transaction context)
    is_unusual_amount = False
    if behavior['avg_amount'] > 0:
        if amt / behavior['avg_amount'] > 3.0:
            is_unusual_amount = True
            
    # Check for night hours (Consistent with extract_time_features)
    is_unusual_time = (time_features['is_night'] == 1)
    
    # Check for new location
    is_location_anomaly = False
    if behavior['usual_locations'] and location not in behavior['usual_locations']:
        is_location_anomaly = True

    # Combined Suspicion Score based on behavioral rules
    is_suspicious = (
        is_unusual_amount or 
        behavior['recent_burst_count'] >= 3 or 
        is_unusual_time or 
        is_location_anomaly or
        amt > 20000 # Safety cap for any high value transaction
    )
    
    user_age = current_user.age or 30 # Default to 30 if null
    
    if is_suspicious:
        # SENIOR PROTECTION (Age 60+) - DUAL OTP SYSTEM
        if user_age >= 60:
            txn_id = "TXN" + str(random.randint(100000, 999999))
            # Create the pending transaction first
            pending_txn = Transaction(
                txn_id=txn_id,
                amount=amt,
                device=device,
                location=location,
                merchant=merchant,
                receiver=receiver_upi,
                email=email,
                prediction='Pending Dual-OTP',
                risk_level='HIGH',
                fraud_probability=0.0,
                requires_cosigner=True
            )
            db.session.add(pending_txn)
            db.session.commit()
            
            # Start the flow using our new helper
            return start_dual_otp_flow(pending_txn)

        # NORMAL ADULT PROTECTION (Age < 60)
        else:
            txn_id = "TXN" + str(random.randint(100000, 999999))
            
            try:
                warning_txn = Transaction(
                    txn_id=txn_id,
                    amount=amt,
                    device=device,
                    location=location,
                    merchant=merchant,
                    receiver=receiver_upi,
                    email=email,
                    prediction='Pending Verification (Scam Warning)',
                    risk_level='HIGH',
                    fraud_probability=100.0,
                    is_verified=False
                )
                db.session.add(warning_txn)
                db.session.commit()
            except Exception as e:
                print(f"Database Error: {e}")
                
            # High-friction Contextual Warning Check
            return render_template('scam_warning.html',
                                   amount=amt,
                                   device=device,
                                   location=location,
                                   merchant=merchant,
                                   phone=phone,
                                   receiver_upi=receiver_upi,
                                   receiver_email=receiver_email,
                                   txn_id=txn_id)

    # If no friction triggered, proceed normally
    return render_template('processing.html', 
                           amount=amt,
                           device=device,
                           location=location,
                           merchant=merchant,
                           phone=phone,
                           receiver=receiver_upi,
                           receiver_email=receiver_email)


@app.route('/verify-dual-otp/<txn_id>', methods=['POST'])
@login_required
def verify_dual_otp(txn_id):
    sender_otp = request.form.get('sender_otp')
    trusted_otp = request.form.get('trusted_otp')
    
    transaction = Transaction.query.filter_by(txn_id=txn_id, email=current_user.email).first_or_404()
    
    if transaction.is_verified:
        return render_template('result.html',
                               result='success',
                               amount=transaction.amount,
                               txn_id=txn_id,
                               prediction={
                                   'result': 'success',
                                   'prediction': 'Already Verified',
                                   'risk_level': '🟢 LOW RISK',
                                   'fraud_probability': 0.0,
                                   'legitimate_probability': 100.0,
                                   'error': False,
                                   'anomalies': ['✅ Transaction was already verified']
                               })

    if transaction.otp_code == sender_otp and transaction.cosigner_otp == trusted_otp:
        # Success! Finalize using helper
        finalize_transaction(transaction)
        flash('Dual-OTP verification successful!')
        return render_template('result.html',
                               result='success',
                               amount=transaction.amount,
                               txn_id=transaction.txn_id,
                               prediction={
                                   'result': 'success', 
                                   'prediction': 'Legitimate', 
                                   'risk_level': '🟢 LOW RISK',
                                   'fraud_probability': 0.0,
                                   'legitimate_probability': 100.0,
                                   'error': False
                               })
    else:
        flash('Invalid OTP combination. Please check both codes and try again.')
        return render_template('dual_verify_otp.html', 
                               amount=transaction.amount, 
                               receiver=transaction.receiver, 
                               trusted_contact=current_user.trusted_contact, 
                               txn_id=txn_id,
                               error="Invalid verification codes.")

@app.route('/resume-dual-otp/<txn_id>', methods=['POST'])
@login_required
def resume_dual_otp(txn_id):
    transaction = Transaction.query.filter_by(txn_id=txn_id, email=current_user.email).first_or_404()
    return render_template('dual_verify_otp.html', 
                           amount=transaction.amount, 
                           receiver=transaction.receiver, 
                           trusted_contact=current_user.trusted_contact, 
                           txn_id=transaction.txn_id)


@app.route('/approve-cosigner/<token>', methods=['GET', 'POST'])
def approve_cosigner(token):
    # Find the pending transaction
    transaction = Transaction.query.filter_by(cosigner_token=token).first_or_404()
    
    # Get the user who initiated it
    sender = User.query.filter_by(email=transaction.email).first()
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'approve':
            transaction.cosigner_approved = True
            db.session.commit()
            
            # Send an email back to the original sender telling them it's approved
            msg = Message(
                subject="✅ Transfer Approved - FraudGuard",
                recipients=[sender.email],
                body=f"Hello {sender.username},\n\nYour Trusted Contact ({sender.trusted_contact}) has approved your transfer of ₹{transaction.amount:,.2f} to {transaction.receiver}.\n\nYou can now log in and complete the transfer from your Transaction History.\n\nFraudGuard Security"
            )
            try:
                mail.send(msg)
            except Exception as e:
                print(f"❌ Failed to notify sender: {e}")
                
            flash(f'Transaction {transaction.txn_id} has been approved successfully. The sender has been notified.')
        
        elif action == 'reject':
            transaction.risk_level = 'CRITICAL'
            transaction.prediction = 'Rejected by Co-Signer'
            db.session.commit()
            flash('Transaction has been rejected and blocked.')
            
    return render_template('cosigner_review.html', transaction=transaction, user=sender)

@app.route('/resume-cosigner/<token>', methods=['POST'])
@login_required
def resume_cosigner(token):
    # Find the pending, approved transaction
    transaction = Transaction.query.filter_by(
        cosigner_token=token, 
        email=current_user.email,
        requires_cosigner=True,
        cosigner_approved=True
    ).first_or_404()
    
    if transaction.is_verified:
        flash("Transaction already completed.")
        return redirect(url_for('history'))
        
    # Finalize it using helper
    if finalize_transaction(transaction):
        return render_template('result.html',
                               result='success',
                               amount=transaction.amount,
                               txn_id=transaction.txn_id,
                               prediction={
                                   'result': 'success', 
                                   'prediction': 'Legitimate', 
                                   'risk_level': '🟢 LOW RISK',
                                   'fraud_probability': 0.0,
                                   'legitimate_probability': 100.0,
                                   'error': False
                               })
    else:
        flash("Error: Insufficient balance.")
        return redirect(url_for('history'))
    
    return render_template('result.html',
                           result='success',
                           amount=transaction.amount,
                           txn_id=transaction.txn_id,
                           prediction={
                               'result': 'success', 
                               'prediction': 'Legitimate', 
                               'risk_level': '🟢 LOW RISK',
                               'fraud_probability': 0.0
                           })

@app.route('/result/<amount>')
@login_required
def result(amount):
    """Display fraud detection result - validation already done in /processing."""
    try:
        amount = float(amount)
    except ValueError:
        return render_template('result.html',
                               result='fraud',
                               amount=0,
                               txn_id="ERROR",
                               prediction={'result': 'fraud', 'error': False, 'fraud_probability': 100},
                               validation_error="Invalid amount format")
    
    # Extract transaction features from URL parameters
    device = request.args.get('device', 'mobile').lower()
    location = request.args.get('location', 'mumbai').lower()
    merchant = request.args.get('merchant', 'other').lower()
    phone = request.args.get('phone', '')
    receiver = request.args.get('receiver', '')
    email = request.args.get('email', '')
    
    # Prepare transaction data for ML model
    transaction_data = {
        'amount': np.log1p(amount),  # Log transform amount
        'hours': time.localtime().tm_hour,
        'is_new_merchant': 1 if not receiver else 0,
        'phone_match': 1,
        'location_match': 1,
        'device_type_code': encode_feature(device, 'device'),
        'merchant_category_code': encode_feature(merchant, 'merchant'),
        'is_weekend': 1 if time.localtime().tm_wday >= 5 else 0,
    }
    
    # Get ML prediction
    prediction = predict_fraud(transaction_data)
    
    # Fallback to basic logic if model not loaded
    if prediction['error']:
        if amount < 5000:
            result = "success"
        elif amount < 15000:
            result = "verify"
        else:
            result = "fraud"
    else:
        result = prediction['result']
    
    txn_id = "TXN" + str(random.randint(100000, 999999))
    
    # Save to Database
    try:
        new_txn = Transaction(
            txn_id=txn_id,
            amount=amount,
            device=device,
            location=location,
            merchant=merchant,
            email=email,
            prediction=prediction['prediction'],
            risk_level=prediction.get('risk_level', 'UNKNOWN'),
            fraud_probability=prediction.get('fraud_probability', 0.0)
        )
        db.session.add(new_txn)
        db.session.commit()
    except Exception as e:
        print(f"Database Error: {e}")
    
    return render_template('result.html',
                           result=result,
                           amount=amount,
                           txn_id=txn_id,
                           prediction=prediction)
@app.route('/result-confirm', methods=['POST'])
@login_required
def result_confirm():
    """Process form data from processing page and display ML prediction result."""
    # Check if we already have a transaction ID from a previous step (like scam warning)
    form_txn_id = request.form.get('txn_id')
    
    # Extract form data from POST
    amount = request.form.get('amount', 0)
    device = request.form.get('device', 'mobile').lower()
    location = request.form.get('location', 'mumbai').lower()
    merchant = request.form.get('merchant', 'other').lower()
    phone = request.form.get('phone', '')
    receiver_upi = request.form.get('receiver', '').strip().lower()
    _, receiver_email = resolve_receiver_upi(receiver_upi)
    email = current_user.email

    try:
        amount = float(amount)
    except ValueError:
        amount = 0
        
    # Fetch behavioral data EARLY to inform the ML features
    behavior = get_user_behavior_features(email)
    
    # Check if this location is new for the user
    is_location_match = 1
    if not behavior['is_new_user'] and behavior['usual_locations']:
        is_location_match = 1 if location in behavior['usual_locations'] else 0

    # Prepare transaction data for ML model
    transaction_data = {
        'amount': np.log1p(amount),
        'hours': time.localtime().tm_hour,
        'is_new_merchant': 1 if not receiver_email else 0,
        'phone_match': 1,
        'location_match': is_location_match,
        'device_type_code': encode_feature(device, 'device'),
        'merchant_category_code': encode_feature(merchant, 'merchant'),
        'is_weekend': 1 if time.localtime().tm_wday >= 5 else 0,
        'device': device,
        'location': location,
        'amount_raw': amount,
        'receiver': receiver_upi
    }

    # Get ENHANCED ML prediction
    prediction = predict_fraud_enhanced(transaction_data, email)
    
    # Fallback logic if model not loaded
    if prediction.get('error'):
        if amount < 5000:
            result = "success"
        elif amount < 15000:
            result = "verify"
        else:
            result = "fraud"
    else:
        result = prediction['result']
    
    # Find or create transaction record
    new_txn = None
    if form_txn_id:
        new_txn = Transaction.query.filter_by(txn_id=form_txn_id, email=email).first()
    
    if new_txn:
        # Update existing transaction
        new_txn.amount = amount
        new_txn.device = device
        new_txn.location = location
        new_txn.merchant = merchant
        new_txn.receiver = receiver_upi
        new_txn.prediction = prediction.get('prediction', 'Unknown')
        new_txn.risk_level = prediction.get('risk_level', 'UNKNOWN')
        new_txn.fraud_probability = prediction.get('fraud_probability', 0.0)
        txn_id = form_txn_id
    else:
        # Create new transaction
        txn_id = "TXN" + str(random.randint(100000, 999999))
        new_txn = Transaction(
            txn_id=txn_id,
            amount=amount,
            device=device,
            location=location,
            merchant=merchant,
            receiver=receiver_upi,
            email=email,
            prediction=prediction.get('prediction', 'Unknown'),
            risk_level=prediction.get('risk_level', 'UNKNOWN'),
            fraud_probability=prediction.get('fraud_probability', 0.0)
        )
        db.session.add(new_txn)

    # If risk is Medium, trigger OTP verification
    if result == "verify":
        # ELDERLY PROTECTION (Age 60+)
        if current_user.age and current_user.age >= 60:
            try:
                new_txn.prediction = 'Pending Dual-OTP (Medium Risk)'
                new_txn.requires_cosigner = True
                db.session.commit()
                return start_dual_otp_flow(new_txn)
            except Exception as e:
                print(f"Error starting senior dual OTP: {e}")
                return render_template('result.html', result="error", amount=amount, txn_id="ERROR", prediction={'error': True})

        # NORMAL ADULT - Single OTP
        otp = str(random.randint(1000, 9999))
        try:
            new_txn.otp_code = otp
            new_txn.is_verified = False
            db.session.commit()
            send_verification_email(email, otp, amount)
            return redirect(url_for('verify_otp', txn_id=txn_id))
        except Exception as e:
            print(f"Database Error during OTP setup: {e}")
            return render_template('result.html', result="error", amount=amount, txn_id="ERROR", prediction={'error': True})

    # Finalize Success or Fraud
    try:
        if result == 'success':
            finalize_transaction(new_txn)
        else:
            db.session.commit()
    except Exception as e:
        print(f"Database Error: {e}")
    
    return render_template('result.html',
                           result=result,
                           amount=amount,
                           txn_id=txn_id,
                           prediction=prediction)

@app.route('/verify-otp/<txn_id>', methods=['GET', 'POST'])
@login_required
def verify_otp(txn_id):
    """Handle 4-digit OTP verification for medium-risk transactions."""
    transaction = Transaction.query.filter_by(txn_id=txn_id).first_or_404()
    
    if transaction.is_verified:
        return render_template('result.html',
                               result='success',
                               amount=transaction.amount,
                               txn_id=txn_id,
                               prediction={
                                   'result': 'success',
                                   'prediction': 'Already Verified',
                                   'risk_level': '🟢 LOW RISK',
                                   'fraud_probability': 0.0,
                                   'legitimate_probability': 100.0,
                                   'error': False,
                                   'anomalies': ['✅ Transaction was already verified']
                               })

    if request.method == 'POST':
        user_otp = request.form.get('otp', '')
        
        if user_otp == transaction.otp_code:
            # Success! Finalize using helper
            if finalize_transaction(transaction, prediction="Legitimate (OTP Verified)"):
                db.session.commit()
            return render_template('result.html',
                                   result="success",
                                   amount=transaction.amount,
                                   txn_id=transaction.txn_id,
                                   prediction={
                                   'prediction': 'Legitimate (OTP Verified)',
                                   'risk_level': '🟢 LOW RISK',
                                   'fraud_probability': 0.0,
                                   'legitimate_probability': 100.0,
                                   'anomalies': ['✅ Transaction verified via email OTP'],
                                   'error': False
                               })
        else:
            return render_template('verify_otp.html', 
                                   txn_id=txn_id, 
                                   amount=transaction.amount,
                                   error="Invalid OTP code. Please try again.")

    return render_template('verify_otp.html', txn_id=txn_id, amount=transaction.amount)



@app.route('/history')
@login_required
def history():
    """Display user's transaction history with statistics."""
    
    # Get user's transactions (most recent first)
    transactions = Transaction.query.filter_by(
        email=current_user.email
    ).order_by(Transaction.timestamp.desc()).limit(50).all()
    
    # Calculate statistics
    stats = None
    if transactions:
        amounts = [t.amount for t in transactions]
        _blocked_kw = ('fraud', 'blocked', 'rejected', 'permanently')
        _legit_kw = ('legitimate', 'approved')
        fraud_count = sum(
            1 for t in transactions
            if t.prediction and any(kw in t.prediction.lower() for kw in _blocked_kw)
        )
        legitimate_count = sum(
            1 for t in transactions
            if t.prediction and any(kw in t.prediction.lower() for kw in _legit_kw)
        )
        
        stats = {
            'total_transactions': len(transactions),
            'avg_amount': round(np.mean(amounts), 2),
            'total_spent': round(sum(amounts), 2),
            'fraud_blocked': fraud_count,
            'legitimate': legitimate_count,
            'max_amount': round(max(amounts), 2),
            'min_amount': round(min(amounts), 2)
        }
    
    return render_template('history.html', 
                         transactions=transactions, 
                         stats=stats)

@app.route('/admin')
@login_required
def admin_dashboard():
    """Master dashboard listing all users with summary stats."""
    if not current_user.is_admin:
        return "Access Denied: Admin privileges required", 403
        
    # Get all users (excluding admins for cleaner list)
    users = User.query.filter_by(is_admin=False).all()
    
    user_stats = []
    for user in users:
        txns = Transaction.query.filter_by(email=user.email).all()
        total_amount = sum(t.amount for t in txns)
        _blocked_keywords = ('fraud', 'blocked', 'rejected', 'permanently')
        fraud_count = sum(
            1 for t in txns
            if t.prediction and any(kw in t.prediction.lower() for kw in _blocked_keywords)
        )
        
        user_stats.append({
            'username': user.username,
            'email': user.email,
            'txn_count': len(txns),
            'total_spent': round(total_amount, 2),
            'fraud_count': fraud_count
        })

    
    # Global metrics
    global_txns = Transaction.query.all()
    _blocked_keywords = ('fraud', 'blocked', 'rejected', 'permanently')
    stats = {
        'total_users': len(users),
        'total_txns': len(global_txns),
        'total_fraud': sum(
            1 for t in global_txns
            if t.prediction and any(kw in t.prediction.lower() for kw in _blocked_keywords)
        )
    }

    return render_template('admin_dashboard.html', users=user_stats, stats=stats)

# Removed balance update route

@app.route('/admin/user/<email>')
@login_required
def admin_user_history(email):
    """View detailed transaction history for a specific user."""
    if not current_user.is_admin:
        return "Access Denied", 403
        
    user = User.query.filter_by(email=email).first_or_404()
    transactions = Transaction.query.filter_by(email=email).order_by(Transaction.timestamp.desc()).all()
    
    return render_template('admin_user_history.html', user=user, transactions=transactions)


@app.route('/api/health')

def health():
    """Check if model is loaded."""
    return jsonify({
        'status': 'ok' if model is not None else 'model_not_loaded',
        'model_loaded': model is not None
    })

if __name__ == '__main__':

    # Auto-initialize database on startup
    try:
        from init_db import init_database
        print("🔄 Checking database setup...")
        init_database()
        print("✅ Database ready")
    except Exception as e:
        print(f"⚠️ Database setup warning: {e}")

    # Load model on startup
    if not load_model():
        print("\n⚠️  WARNING: Model not found. Run the following command:")
        print("   python train_model.py")
        print("\nThe app will fall back to basic if-condition logic.")
    
    # Run on port 5001 to avoid AirPlay conflict
    app.run(debug=True, port=5001)
    
    app.run(debug=True)