"""
Fraud Detection Model Training Script
Downloads the Credit Card Fraud Detection dataset from Kaggle and trains an XGBoost model.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import pickle
import warnings

warnings.filterwarnings('ignore')

def download_and_prepare_data():
    """
    Download fraud detection data. 
    For simplicity, we'll create a synthetic balanced dataset if Kaggle API is not available.
    """
    try:
        # Try to load from local kaggle dataset
        df = pd.read_csv('creditcard.csv')
        print(f"✓ Loaded dataset from local file: {df.shape}")
    except FileNotFoundError:
        print("📥 Kaggle API not configured. Creating synthetic training data...")
        # Create synthetic fraud detection dataset
        np.random.seed(42)
        n_samples = 5000
        
        # Legitimate transactions
        legitimate = pd.DataFrame({
            'amount': np.random.exponential(scale=50, size=n_samples),
            'hours': np.random.randint(0, 24, n_samples),
            'is_new_merchant': np.random.choice([0, 1], n_samples, p=[0.8, 0.2]),
            'phone_match': np.random.choice([0, 1], n_samples, p=[0.9, 0.1]),
            'location_match': np.random.choice([0, 1], n_samples, p=[0.85, 0.15]),
            'device_type_code': np.random.choice([1, 2, 3], n_samples),
            'merchant_category_code': np.random.choice([1, 2, 3, 4, 5], n_samples),
            'is_weekend': np.random.choice([0, 1], n_samples, p=[0.7, 0.3]),
            'fraud': 0
        })
        
        # Fraudulent transactions
        fraudulent = pd.DataFrame({
            'amount': np.random.exponential(scale=150, size=n_samples // 10),
            'hours': np.random.choice([2, 3, 4, 23], n_samples // 10),
            'is_new_merchant': np.random.choice([0, 1], n_samples // 10, p=[0.2, 0.8]),
            'phone_match': np.random.choice([0, 1], n_samples // 10, p=[0.3, 0.7]),
            'location_match': np.random.choice([0, 1], n_samples // 10, p=[0.2, 0.8]),
            'device_type_code': np.random.choice([1, 2, 3], n_samples // 10),
            'merchant_category_code': np.random.choice([1, 2, 3, 4, 5], n_samples // 10),
            'is_weekend': np.random.choice([0, 1], n_samples // 10, p=[0.4, 0.6]),
            'fraud': 1
        })
        
        df = pd.concat([legitimate, fraudulent], ignore_index=True).sample(frac=1).reset_index(drop=True)
        print(f"✓ Generated synthetic dataset: {df.shape}")
    
    return df

def train_model(df):
    """Train XGBoost fraud detection model."""
    
    # Prepare features and target
    X = df.drop('fraud', axis=1)
    y = df['fraud']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train XGBoost model
    print("\n🤖 Training XGBoost model...")
    model = XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_test_scaled, y_test)],
        verbose=False
    )
    
    # Evaluate
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    print("\n📊 Model Performance:")
    print(f"ROC-AUC Score: {roc_auc_score(y_test, y_pred_proba):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Legitimate', 'Fraudulent']))
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    
    # Save model and scaler
    with open('fraud_model.pkl', 'wb') as f:
        pickle.dump(model, f)
    
    with open('fraud_scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save feature names
    with open('fraud_features.pkl', 'wb') as f:
        pickle.dump(list(X.columns), f)
    
    print("\n✅ Model saved as 'fraud_model.pkl'")
    print("✅ Scaler saved as 'fraud_scaler.pkl'")
    print("✅ Features saved as 'fraud_features.pkl'")

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Fraud Detection Model Training")
    print("=" * 60)
    
    # Download/prepare data
    df = download_and_prepare_data()
    
    # Train model
    train_model(df)
    
    print("\n" + "=" * 60)
    print("✨ Training Complete! Ready to integrate with Flask app.")
    print("=" * 60)
