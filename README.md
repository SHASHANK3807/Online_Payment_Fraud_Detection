# Online Payment Fraud Detection

An end-to-end machine learning web application for detecting potentially fraudulent online payment transactions. The system uses an **XGBoost classification model** to analyze transaction-related features and classify transactions as **legitimate or potentially fraudulent**.

The project combines a trained machine learning model with a **Flask-based web application**, allowing users to interact with the fraud detection system through a web interface.

## Features

- Machine learning-based fraud classification
- XGBoost-powered prediction model
- Transaction feature preprocessing and standardization
- Fraud probability/prediction workflow
- Flask web application
- Saved ML model, scaler, and feature configuration
- Input validation for transaction data
- Database integration for application data
- Modular training and application architecture

## Machine Learning Workflow

The fraud detection pipeline includes:

1. Data preparation and preprocessing
2. Feature selection
3. Train-test splitting with stratification
4. Feature scaling using `StandardScaler`
5. XGBoost model training
6. Model evaluation using:
   - ROC-AUC
   - Classification Report
   - Confusion Matrix
7. Serialization of the trained model and preprocessing artifacts
8. Integration of the trained model with the Flask application

## Technology Stack

- **Python**
- **Flask**
- **XGBoost**
- **Scikit-learn**
- **Pandas**
- **NumPy**
- **HTML / CSS / JavaScript**
- **SQLite / Database**
- **Pickle**

## Project Structure

```text
Online_Payment_Fraud_Detection/
│
├── app.py                  # Flask application
├── train_model.py          # Model training pipeline
├── models.py               # Database/application models
├── validators.py           # Input validation
├── config.py               # Application configuration
├── init_db.py              # Database initialization
├── fix_db.py               # Database utility
│
├── fraud_model.pkl         # Trained XGBoost model
├── fraud_scaler.pkl        # Feature scaler
├── fraud_features.pkl      # Model feature configuration
│
├── templates/              # HTML templates
├── static/                 # CSS, JavaScript and static assets
├── md_files/               # Project documentation
│
├── requirements.txt        # Python dependencies
└── .env.example            # Environment configuration template
```

## Model

The system uses **XGBoost**, a gradient-boosted decision tree algorithm well suited for classification problems.

During training, the project:

- Splits the dataset into training and testing sets
- Applies standardization to the input features
- Trains an XGBoost classifier
- Evaluates prediction performance using ROC-AUC, classification metrics, and a confusion matrix
- Saves the trained model and preprocessing components for use by the Flask application

## Purpose

The goal of this project is to demonstrate how machine learning can be integrated into a web-based financial security application to identify suspicious transaction patterns and assist in fraud detection.

> **Note:** This project is intended for educational and demonstration purposes and is not a production banking fraud-prevention system.
