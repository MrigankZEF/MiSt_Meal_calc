"""
Small metrics utilities for the meal calculator.
Functions:
- convert_to_kg(amount, unit, matched_name, piece_weights)
- per100g_from_perkg(perkg)
"""

def per100g_from_perkg(perkg):
    try:
        return float(perkg) * 0.1
    except Exception:
        return None


def convert_to_kg(amount, unit, matched_name, piece_weights=None):
    """Convert an amount+unit to kilograms. piece_weights is a dict name->grams."""
    unit = (unit or 'g').lower()
    try:
        amt = float(amount)
    except Exception:
        amt = 0.0
    if unit in ['g','gram','grams']:
        return amt/1000.0
    if unit in ['kg','kilogram','kilograms']:
        return amt
    if unit in ['mg','milligram','milligrams']:
        return amt/1e6
    if unit in ['l','liter','litre','liters','litres','ml','milliliter','millilitre']:
        # heuristic: density ~= 1 g/ml
        if unit.startswith('m'):
            return amt/1000.0
        else:
            return amt
    if unit in ['piece','pieces','pc','pcs']:
        grams = None
        if piece_weights:
            grams = piece_weights.get(matched_name.lower()) if matched_name else None
            if grams is None:
                grams = piece_weights.get(str(matched_name).lower()) if matched_name else None
        if grams is None:
            grams = 100.0
        return grams/1000.0
    # unknown unit: assume grams
    return amt/1000.0
