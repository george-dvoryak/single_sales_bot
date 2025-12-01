# payments/hmac_verifier.py
"""HMAC signature verification for ProDAMUS webhooks (based on PHP Hmac class)."""

import hmac
import hashlib
import json
from typing import Any, Dict, Union


class Hmac:
    """HMAC signature creation and verification for ProDAMUS."""
    
    @staticmethod
    def create(data: Dict[str, Any], key: str, algo: str = 'sha256') -> str:
        """
        Create HMAC signature from data.
        
        Args:
            data: Dictionary of data to sign
            key: Secret key for HMAC
            algo: Hash algorithm (default: 'sha256')
        
        Returns:
            HMAC signature as hex string, or empty string on error
        """
        try:
            # Check if algorithm is supported
            if algo not in hashlib.algorithms_available:
                print(f"Hmac: Algorithm '{algo}' not available")
                return ""
            
            # Convert data to dict if it's not already
            if not isinstance(data, dict):
                data = dict(data)
            
            # Recursively convert all values to strings
            def convert_to_strings(obj: Any) -> Any:
                """Recursively convert all values to strings."""
                if isinstance(obj, dict):
                    return {k: convert_to_strings(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_to_strings(item) for item in obj]
                else:
                    return str(obj)
            
            data = convert_to_strings(data)
            
            # Recursively sort by keys
            def recursive_sort(obj: Any) -> Any:
                """Recursively sort dictionaries by keys."""
                if isinstance(obj, dict):
                    # Sort keys and recursively sort values
                    sorted_dict = {}
                    for k in sorted(obj.keys()):
                        sorted_dict[k] = recursive_sort(obj[k])
                    return sorted_dict
                elif isinstance(obj, list):
                    # Sort list items if they're dicts
                    return [recursive_sort(item) for item in obj]
                else:
                    return obj
            
            data = recursive_sort(data)
            
            # JSON encode with unescaped unicode (like JSON_UNESCAPED_UNICODE in PHP)
            json_data = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            
            # Calculate HMAC
            hash_func = getattr(hashlib, algo)
            signature = hmac.new(
                key.encode('utf-8'),
                json_data.encode('utf-8'),
                hash_func
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            print(f"Hmac.create() error: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    @staticmethod
    def verify(data: Dict[str, Any], key: str, sign: str, algo: str = 'sha256') -> bool:
        """
        Verify HMAC signature.
        
        Args:
            data: Dictionary of data to verify
            key: Secret key for HMAC
            sign: Received signature to verify against
            algo: Hash algorithm (default: 'sha256')
        
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not sign:
                print("Hmac.verify(): Empty signature provided")
                return False
            
            # Create signature from data
            calculated_sign = Hmac.create(data, key, algo)
            
            if not calculated_sign:
                print("Hmac.verify(): Failed to create signature")
                return False
            
            # Compare signatures (case-insensitive, like PHP strtolower)
            is_valid = calculated_sign.lower() == sign.lower()
            
            if not is_valid:
                print(f"Hmac.verify(): Signature mismatch")
                print(f"  Calculated: {calculated_sign}")
                print(f"  Received:   {sign}")
            
            return is_valid
            
        except Exception as e:
            print(f"Hmac.verify() error: {e}")
            import traceback
            traceback.print_exc()
            return False

