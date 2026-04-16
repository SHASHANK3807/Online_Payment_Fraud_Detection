# Project Overview: ML-Powered Fraud Detection Web Application

This project is a **Machine Learning-powered Fraud Detection Web Application**. It uses a Flask (Python) backend and an **XGBoost** machine learning model to evaluate financial transactions in real-time.

When a user submits transaction details (like the transfer amount, device type, location, and merchant category), the system runs those details through the trained ML model. The model calculates the probability of the transaction being fraudulent and instantly returns a risk assessment (Low, Medium, or High risk) along with a percentage score.

---

## 🔄 Program Flow & Architecture

The system's flow can be broken down into two main phases: **Model Training** (offline) and **Web Application Inference** (live).

### 1. Model Training & Preparation (`train_model.py`)
Before the web app can predict anything, the ML model needs to learn what fraud looks like.
* **Data Ingestion:** The `train_model.py` script generates a synthetic dataset (or loads real data like a Kaggle CSV) containing thousands of samples of both legitimate and fraudulent transactions.
* **Preprocessing:** The data is split into training and testing sets. Numeric fields are scaled down to normalized values using a `StandardScaler`.
* **Training:** An XGBoost Classifier (a powerful decision-tree-based algorithm) is trained on the data to recognize complex fraud patterns (achieving ~99% accuracy).
* **Exporting Artifacts:** Once trained, the script saves three "pickle" files (`.pkl`):
  * `fraud_model.pkl` (The brain/XGBoost model)
  * `fraud_scaler.pkl` (The tool used to normalize future inputs)
  * `fraud_features.pkl` (A list of required input features to guarantee consistency)

### 2. Web Application Setup (`app.py` startup)
* When you run `python app.py`, the Flask server starts.
* During startup, the `load_model()` function immediately loads the three `.pkl` files into memory. This ensures that the ML model is always ready to make ultra-fast predictions (<100ms) without having to reload from the disk for every user request.

### 3. User Interaction & Live Data Flow
This is what happens when a user attempts a transaction:
1. **User Interface (`index.html`)**: The user fills out a web form with transaction details (amount, hour of the day, device type, merchant category, etc.).
2. **Form Submission (`/processing`)**: The form is submitted via an HTTP POST request. A temporary `processing.html` page might show a loading state mimicking backend checks.
3. **Feature Engineering**: The app captures the raw input and prepares it for the ML model inside a background extraction function. It does things like:
   * Taking the mathematical `log()` of the transaction amount.
   * Converting text like `device="mobile"` into numeric codes (e.g., `1`).
   * Structuring this into a specific 8-feature numerical vector.
4. **ML Inference (`predict_fraud()` inside `app.py`)**: 
   * The feature vector is passed through the pre-loaded `fraud_scaler` to normalize the numbers exactly as they were during training.
   * The scaled vector is passed to the `XGBoost` model, which outputs a **Fraud Probability** (e.g., `0.08` meaning 8% chance of fraud).
5. **Decision & Risk Thresholds**: The backend evaluates the returned percentage against predefined thresholds:
   * 🟢 **< 40% (Low Risk)**: The transaction auto-passes as legitimate.
   * 🟡 **40% - 70% (Medium Risk)**: Flagged for verification.
   * 🔴 **> 70% (High Risk)**: Blocked as highly suspicious/fraudulent.
6. **Result (`result.html`)**: The system renders the final results page to the user, displaying the risk level, the exact fraud probability (e.g., "8% fraud"), and whether the transaction was approved or declined.

### Summary
In short, it's a very clean, production-styled pipeline where **user inputs → Flask Backend → ML Preprocessing → XGBoost Prediction → Risk Assessment → UI Output**.
