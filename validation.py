from ipaddress import IPv4Interface
import traceback

def is_valid_ip4(address):
    try:
        interface = IPv4Interface(address)
        return True,None
    except Exception:
        return False,traceback.format_exc()
# print(ipv4_mask_len('255.255.224.0'))
