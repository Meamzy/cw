"""
Dummy additional_functions.py to allow norn.py to import.
The actual functions will be mocked during testing in tests/test_norn.py.
"""

def is_valid_ip4(ip_string):
    """Dummy implementation."""
    print(f"Warning: Dummy is_valid_ip4 called with: {ip_string}")
    if isinstance(ip_string, str) and "/" in ip_string:
        return True, ""
    return False, "Dummy: Invalid IP format"

def form_data_to_addr_mask_pairs(form_data):
    """Dummy implementation."""
    print(f"Warning: Dummy form_data_to_addr_mask_pairs called with: {form_data}")
    return []

def generate_diff_lists(new_list, old_list):
    """Dummy implementation."""
    print(f"Warning: Dummy generate_diff_lists called with: new={new_list}, old={old_list}")
    return [], [] # delete_diff, add_diff
