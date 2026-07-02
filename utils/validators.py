"""
Validation utilities for the ERP system
"""
import re
from datetime import datetime, date
from typing import Optional, Tuple
from .constants import (MaterialConstants, BatchConstants, 
                      UnitOfMeasure, ValidationMessages)

def validate_code(code: str) -> Tuple[bool, str]:
    """
    Validate material code format
    Format: M1234567
    """
    if not code:
        return False, ValidationMessages.REQUIRED_FIELD
        
    if not re.match(MaterialConstants.CODE_REGEX, code):
        return False, ValidationMessages.INVALID_CODE
        
    return True, ""

class MaterialValidator:
    """Material data validator"""
    
    @staticmethod
    def validate_code(code: str) -> Tuple[bool, str]:
        """
        Validate material code format
        Format: M1234567
        """
        return validate_code(code)

    @staticmethod
    def validate_name(name: str) -> Tuple[bool, str]:
        """Validate material name"""
        if not name:
            return False, ValidationMessages.REQUIRED_FIELD
            
        if len(name) < MaterialConstants.NAME_MIN_LENGTH:
            return False, ValidationMessages.NAME_TOO_SHORT
            
        if len(name) > MaterialConstants.NAME_MAX_LENGTH:
            return False, ValidationMessages.NAME_TOO_LONG
            
        return True, ""

    @staticmethod
    def validate_unit(unit: str) -> Tuple[bool, str]:
        """Validate unit of measure"""
        if not unit:
            return False, ValidationMessages.REQUIRED_FIELD
            
        if unit not in UnitOfMeasure.get_all_units():
            return False, ValidationMessages.INVALID_UNIT
            
        return True, ""

    @staticmethod
    def validate_quantity(quantity: float) -> Tuple[bool, str]:
        """Validate quantity value"""
        if quantity < MaterialConstants.MIN_QUANTITY:
            return False, ValidationMessages.INVALID_QUANTITY
            
        if quantity > MaterialConstants.MAX_QUANTITY:
            return False, f"數量不能超過 {MaterialConstants.MAX_QUANTITY}"
            
        return True, ""

    @staticmethod
    def validate_temperature(temp: Optional[float]) -> Tuple[bool, str]:
        """Validate storage temperature"""
        if temp is None:
            return True, ""
            
        if not MaterialConstants.MIN_TEMP <= temp <= MaterialConstants.MAX_TEMP:
            return False, ValidationMessages.INVALID_TEMPERATURE
            
        return True, ""

class BatchValidator:
    """Batch data validator"""
    
    @staticmethod
    def validate_batch_number(batch_number: str) -> Tuple[bool, str]:
        """
        Validate batch number format
        Format: BYYYYMMDDXXX
        """
        if not batch_number:
            return False, ValidationMessages.REQUIRED_FIELD
            
        if not re.match(BatchConstants.BATCH_REGEX, batch_number):
            return False, ValidationMessages.INVALID_BATCH
            
        # Validate date part
        try:
            date_str = batch_number[1:9]
            datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            return False, "批號中的日期無效"
            
        return True, ""

    @staticmethod
    def validate_expiry_date(mfg_date: date, expiry_date: date) -> Tuple[bool, str]:
        """Validate expiry date"""
        if not expiry_date:
            return False, "效期不能為空"
            
        if expiry_date <= mfg_date:
            return False, "效期必須晚於製造日期"
            
        # Check maximum expiry period
        max_expiry = mfg_date.replace(year=mfg_date.year + BatchConstants.MAX_EXPIRY_YEARS)
        if expiry_date > max_expiry:
            return False, f"效期不能超過{BatchConstants.MAX_EXPIRY_YEARS}年"
            
        return True, ""

def generate_next_batch_number(current_max: Optional[str] = None) -> str:
    """Generate next batch number"""
    today = datetime.now()
    date_part = today.strftime("%Y%m%d")
    
    if not current_max:
        return f"B{date_part}001"
        
    # Extract sequence number and increment
    seq = int(current_max[-3:])
    next_seq = str(seq + 1).zfill(3)
    
    return f"B{date_part}{next_seq}"

def validate_material_data(data: dict) -> Tuple[bool, str]:
    """Validate complete material data"""
    validator = MaterialValidator()
    
    # Check required fields
    for field, value in data.items():
        if field == 'code':
            is_valid, message = validator.validate_code(value)
        elif field == 'name':
            is_valid, message = validator.validate_name(value)
        elif field == 'unit':
            is_valid, message = validator.validate_unit(value)
        elif field == 'quantity':
            is_valid, message = validator.validate_quantity(float(value))
        elif field == 'storage_temp' and value is not None:
            is_valid, message = validator.validate_temperature(float(value))
        else:
            continue
            
        if not is_valid:
            return False, message
            
    return True, ""