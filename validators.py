"""
Transaction Validators Module
Validates transaction input data before ML prediction
"""

import re
from typing import Tuple


class TransactionValidator:
    """Validates transaction input data for format and logical consistency"""
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, str]:
        """
        Validate Indian phone number (10 digits, starts with 6-9)
        
        Args:
            phone: Phone number string
            
        Returns:
            (is_valid: bool, message: str)
        """
        if not phone or phone.strip() == '':
            return False, "Phone number is required"
        
        # Remove spaces, dashes, +91, etc.
        clean_phone = re.sub(r'\D', '', str(phone))
        
        # Check length
        if len(clean_phone) != 10:
            return False, f"Phone must be 10 digits (got {len(clean_phone)})"
        
        # Check if numeric
        if not clean_phone.isdigit():
            return False, "Phone must contain only numbers"
        
        # Check if starts with valid prefix (6-9 for Indian numbers)
        if clean_phone[0] not in '6789':
            return False, "Invalid phone prefix (must start with 6-9)"
        
        return True, "Valid phone number"
    
    @staticmethod
    def validate_amount(amount: str) -> Tuple[bool, str]:
        """
        Validate transaction amount (positive, within limits)
        
        Args:
            amount: Amount as string or number
            
        Returns:
            (is_valid: bool, message: str)
        """
        if not amount:
            return False, "Amount is required"
        
        # Try to convert to float
        try:
            amt = float(amount)
        except (ValueError, TypeError):
            return False, f"Amount must be a number (got '{amount}')"
        
        # Check if positive
        if amt <= 0:
            return False, f"Amount must be positive (got ₹{amt})"
        
        # Check if less than 1 rupee (minimum transaction)
        if amt < 1:
            return False, "Amount must be at least ₹1"
        
        # Check maximum limit (₹500,000)
        if amt > 500000:
            return False, f"Amount exceeds maximum limit (₹500,000). Got ₹{amt:,.0f}"
        
        # Check for reasonable decimal places
        if amt * 100 != int(amt * 100):
            return False, "Amount can have maximum 2 decimal places"
        
        return True, f"Valid amount ₹{amt:,.0f}"
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """
        Validate email format
        
        Args:
            email: Email address string
            
        Returns:
            (is_valid: bool, message: str)
        """
        if not email or email.strip() == '':
            return False, "Email is required"
        
        email = email.strip()
        
        # Email regex pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(pattern, email):
            return False, f"Invalid email format: {email}"
        
        # Additional checks
        if len(email) > 254:
            return False, "Email is too long (max 254 characters)"
        
        # Check for consecutive dots
        if '..' in email:
            return False, "Email cannot contain consecutive dots"
        
        return True, "Valid email"
    
    @staticmethod
    def validate_upi(upi: str) -> Tuple[bool, str]:
        """
        Validate UPI ID format (name@bankname)
        
        Args:
            upi: UPI ID string
            
        Returns:
            (is_valid: bool, message: str)
        """
        if not upi or upi.strip() == '':
            return False, "UPI ID is required"
        
        upi = upi.strip().lower()
        
        # Basic UPI format: username@bankname
        pattern = r'^[a-z0-9._-]+@[a-z]{3,}$'
        
        if not re.match(pattern, upi):
            return False, f"Invalid UPI format: {upi}. Expected format: name@bankname"
        
        # Check length
        if len(upi) > 60:
            return False, "UPI ID is too long"
        
        # Valid UPI providers in India
        valid_providers = {
            'airtel', 'airtelpaymentsbank', 'allbank', 'anbl', 'aubank',
            'axis', 'axisbank', 'barodampay', 'baroda', 'bikanebank',
            'boi', 'boiaxis', 'citi', 'centralbank', 'citibank',
            'cmsbank', 'cmsnap', 'coop', 'dbs', 'denom', 'deutsche',
            'dhfl', 'disha', 'dlb', 'dms', 'ezeepay', 'federal',
            'federalbank', 'fbl', 'gic', 'hbank', 'hdfc', 'hdfcbank',
            'ibank', 'icic', 'icicibank', 'idbi', 'idbibank', 'idfc',
            'idfcbank', 'iifl', 'imobile', 'indusind', 'iob', 'iobap',
            'indiagold', 'indianbank', 'indus', 'indusindbank', 'kbl',
            'kmbl', 'kotak', 'kmblwap', 'lbl', 'obc', 'okhdfcbank',
            'okaxis', 'okicici', 'okhbank', 'okpnb', 'okaxis', 'payworld',
            'pnb', 'pnbsp', 'postbank', 'rbl', 'sbi', 'sbibank', 'sc',
            'scwswap', 'solapur', 'svc', 'syndbank', 'ubi', 'union',
            'unionbank', 'unitedbank', 'utbi', 'vmhbank', 'vijaya',
            'vijabank', 'yesbank', 'ybl', 'upi', 'fraudguard'
        }
        
        bank_name = upi.split('@')[1]
        
        if bank_name not in valid_providers:
            return True, f"UPI format is valid (Note: {bank_name} may not be a recognized provider)"
        
        return True, f"Valid UPI ID: {upi}"
    
    @staticmethod
    def validate_name(name: str) -> Tuple[bool, str]:
        """
        Validate person's name
        
        Args:
            name: Name string
            
        Returns:
            (is_valid: bool, message: str)
        """
        if not name or name.strip() == '':
            return False, "Name is required"
        
        name = name.strip()
        
        # Check length
        if len(name) < 2:
            return False, "Name must be at least 2 characters"
        
        if len(name) > 100:
            return False, "Name is too long (max 100 characters)"
        
        # Check for only letters and spaces
        if not re.match(r"^[a-zA-Z\s'-]+$", name):
            return False, "Name can only contain letters, spaces, hyphens, and apostrophes"
        
        return True, f"Valid name: {name}"
    
    @staticmethod
    def validate_location(location: str) -> Tuple[bool, str]:
        """
        Validate transaction location
        
        Args:
            location: City name
            
        Returns:
            (is_valid: bool, message: str)
        """
        valid_locations = {
            'mumbai', 'delhi', 'bangalore', 'hyderabad', 'kolkata',
            'chennai', 'pune', 'jaipur', 'lucknow', 'chandigarh',
            'ahmedabad', 'surat', 'indore', 'bhopal', 'visakhapatnam'
        }
        
        if not location or location.strip() == '':
            return False, "Location is required"
        
        location_lower = location.strip().lower()
        
        if location_lower not in valid_locations:
            return False, f"Invalid location: {location}. Valid cities: {', '.join(sorted(valid_locations))}"
        
        return True, f"Valid location: {location}"
    
    @staticmethod
    def validate_all(transaction_data: dict) -> Tuple[bool, str, dict]:
        """
        Validate all transaction data
        
        Args:
            transaction_data: Dictionary with transaction fields
            
        Returns:
            (is_valid: bool, error_message: str, validation_results: dict)
        """
        validation_results = {
            'amount': None,
            'phone': None,
            'email': None,
            'upi': None,
            'location': None
        }
        
        # Validate amount
        is_valid, msg = TransactionValidator.validate_amount(
            transaction_data.get('amount')
        )
        validation_results['amount'] = {'valid': is_valid, 'message': msg}
        if not is_valid:
            return False, f"❌ Amount Error: {msg}", validation_results
        
        # Validate phone
        phone = transaction_data.get('phone', '')
        if phone:  # Only validate if provided
            is_valid, msg = TransactionValidator.validate_phone(phone)
            validation_results['phone'] = {'valid': is_valid, 'message': msg}
            if not is_valid:
                return False, f"❌ Phone Error: {msg}", validation_results
        
        # Validate email
        email = transaction_data.get('email', '')
        if email:  # Only validate if provided
            is_valid, msg = TransactionValidator.validate_email(email)
            validation_results['email'] = {'valid': is_valid, 'message': msg}
            if not is_valid:
                return False, f"❌ Email Error: {msg}", validation_results
        
        # Validate UPI receiver
        upi = transaction_data.get('receiver', '')
        if upi:  # Only validate if provided
            is_valid, msg = TransactionValidator.validate_upi(upi)
            validation_results['upi'] = {'valid': is_valid, 'message': msg}
            if not is_valid:
                return False, f"❌ UPI Error: {msg}", validation_results
        
        
        # Validate location
        location = transaction_data.get('location', '')
        if location:  # Only validate if provided
            is_valid, msg = TransactionValidator.validate_location(location)
            validation_results['location'] = {'valid': is_valid, 'message': msg}
            if not is_valid:
                return False, f"❌ Location Error: {msg}", validation_results
        
        return True, "✅ All validations passed", validation_results


# Quick validation checks
def is_valid_phone(phone: str) -> bool:
    """Quick check if phone is valid"""
    is_valid, _ = TransactionValidator.validate_phone(phone)
    return is_valid


def is_valid_amount(amount) -> bool:
    """Quick check if amount is valid"""
    is_valid, _ = TransactionValidator.validate_amount(amount)
    return is_valid


def is_valid_email(email: str) -> bool:
    """Quick check if email is valid"""
    is_valid, _ = TransactionValidator.validate_email(email)
    return is_valid
