import os
import logging # Added
from nornir import InitNornir
from nornir.core.inventory import Host
import nornir_napalm
from nornir_utils.plugins.functions import print_result, print_title
from nornir.core.task import Result, Task as task
from nornir_jinja2.plugins.tasks import template_file, template_string
from nornir_netmiko.tasks import netmiko_send_config
from nornir_napalm.plugins.tasks import napalm_get
import json
# import os # Already imported at the top
from ciscoconfparse import CiscoConfParse
from additional_functions import is_valid_ip4,form_data_to_addr_mask_pairs,generate_diff_lists

# --- Logging Setup ---
logger = logging.getLogger(__name__) # Logger for norn.py
# --- End Logging Setup ---

# def allocate_interface(task,interface_name: str,ip_address: str,ip_mask: str):
#     inteface_config = task.run(task=template_file,template="interface.j2",path="configuration/",
#     interface_name=interface_name,ip_address=ip_address,ip_mask=ip_mask)
#     inteface_config_output = inteface_config.result
#     inteface_config_send = inteface_config_output.splitlines()
#     task.run(task=netmiko_send_config,config_commands=inteface_config_send)

# print_title("Running the interfaces config")
# result = nr.run(task=allocate_interface,interface_name="FastEthernet3/0 ",ip_address="10.10.11.3",ip_mask="255.255.255.0")

def get_nornir_runner_with_creds():
    """Initializes Nornir with credentials from environment variables."""
    logger.debug("Attempting to initialize Nornir runner.")
    username = os.environ.get("NORNIR_USERNAME")
    password = os.environ.get("NORNIR_PASSWORD")

    if not username or not password:
        logger.error("NORNIR_USERNAME or NORNIR_PASSWORD environment variables not set.")
        raise ValueError("NORNIR_USERNAME and NORNIR_PASSWORD environment variables must be set.")
    
    logger.info("Nornir credentials loaded from environment variables.")
    try:
        nr = InitNornir(
            config_file="nornir_configuration/config.yaml",
            inventory={
                "options": {
                    "defaults": {
                        "username": username,
                        "password": password,
                    }
                }
            }
        )
        logger.debug("Nornir runner initialized successfully.")
        return nr
    except Exception as e:
        logger.error(f"Failed to initialize Nornir: {str(e)}", exc_info=True)
        raise  # Re-raise the exception after logging

def list_all_hosts():
    logger.info("Listing all hosts.")
    try:
        nr = get_nornir_runner_with_creds()
        host_keys = list(nr.inventory.hosts.keys())
        logger.debug(f"Found hosts: {host_keys}")
        return host_keys
    except Exception as e:
        logger.error(f"Error listing all hosts: {str(e)}", exc_info=True)
        raise # Re-raise to be caught by Flask routes

def list_host_interfaces_info(host:str):
    logger.info(f"Listing interface info for host: {host}")
    try:
        nr = get_nornir_runner_with_creds()
        nr_filtered = nr.filter(name=host)
        if not nr_filtered.inventory.hosts:
            logger.warning(f"Host '{host}' not found in Nornir inventory for interface info.")
            raise ValueError(f"Host '{host}' not found in Nornir inventory.")
        
        logger.debug(f"Running napalm_get 'get_interfaces' for host {host}.")
        intefaces_info_result = nr_filtered.run(task=napalm_get, getters=["get_interfaces"])
        logger.debug(f"Running napalm_get 'get_interfaces_ip' for host {host}.")
        interfaces_ip_result = nr_filtered.run(task=napalm_get, getters=["get_interfaces_ip"])

        # Check individual task failures more robustly
        if intefaces_info_result.failed:
            err_msg = intefaces_info_result[host][0].result if host in intefaces_info_result and intefaces_info_result[host] else "NAPALM task 'get_interfaces' failed without specific result."
            logger.error(f"napalm_get 'get_interfaces' failed for host {host}. NAPALM Result: {err_msg}")
            raise ConnectionError(f"Failed to get interface details for {host}. NAPALM Result: {err_msg}")
        
        if interfaces_ip_result.failed:
            err_msg = interfaces_ip_result[host][0].result if host in interfaces_ip_result and interfaces_ip_result[host] else "NAPALM task 'get_interfaces_ip' failed without specific result."
            logger.error(f"napalm_get 'get_interfaces_ip' failed for host {host}. NAPALM Result: {err_msg}")
            raise ConnectionError(f"Failed to get interface IP details for {host}. NAPALM Result: {err_msg}")

        interfaces_data = intefaces_info_result[host][0].result.get("get_interfaces", {})
        interfaces_ip_data = interfaces_ip_result[host][0].result.get("get_interfaces_ip", {})
        logger.info(f"Successfully retrieved interface info for host: {host}")
        return (interfaces_data, interfaces_ip_data)

    except ValueError as ve: 
        logger.error(f"ValueError in list_host_interfaces_info for {host}: {str(ve)}", exc_info=True) 
        raise
    except ConnectionError as ce: 
        logger.error(f"ConnectionError in list_host_interfaces_info for {host}: {str(ce)}", exc_info=True) 
        raise
    except Exception as e:
        logger.error(f"Error listing host interfaces info for {host}: {str(e)}", exc_info=True)
        raise

def configure_interface(task,chosen_interface: str,ip_address: str,ip_mask: str,description: str, enabled_status):
    # This function is a Nornir task, logging here will be per-host within Nornir's execution
    task_logger = logging.getLogger(f"nornir.task.{task.host.name}") 
    task_logger.info(f"Starting 'configure_interface' for interface {chosen_interface} with IP {ip_address}/{ip_mask} on host {task.host.name}")
    
    shut_no_shut = "no shut" if enabled_status=="true" else "shut"
    
    try:
        inteface_config_template = task.run(
            task=template_file,
            template="interface.j2",
            path="configuration/",
            chosen_interface=chosen_interface,
            ip_address=ip_address,
            ip_mask=ip_mask,
            description=description,
            shut_no_shut=shut_no_shut
        )
        inteface_config_output = inteface_config_template.result
        inteface_config_send = inteface_config_output.splitlines()
        task_logger.debug(f"Generated config for {chosen_interface} on {task.host.name}: {inteface_config_send}")

        send_config_result = task.run(task=netmiko_send_config, config_commands=inteface_config_send)
        
        if send_config_result.failed:
            task_logger.error(f"netmiko_send_config failed for {chosen_interface} on {task.host.name}. Error: {send_config_result.result}")
            # Nornir will raise an exception that will be caught by the calling .run() method if any task fails.
        else:
            task_logger.info(f"Successfully configured interface {chosen_interface} on {task.host.name}.")
        # The result of netmiko_send_config is implicitly part of the task's overall result.
            
    except Exception as e:
        task_logger.error(f"Exception during 'configure_interface' for {chosen_interface} on {task.host.name}: {str(e)}", exc_info=True)
        # Re-raise to ensure Nornir marks the task as failed and the exception is propagated.
        raise

def configure_interface_request(data:dict):
    logger.info(f"Received interface configuration request with data keys: {list(data.keys())}") # Log keys to avoid large data dumps
    # print(data) # Replaced by logger
    
    description = data.get("description", "None") # Default if not present, or handle as required
    ipv4 = data.get("ipv4_address")
    ipv4_mask = data.get("ipv4_mask")
    enabled_status = data.get("enabled_status")
    chosen_interface = data.get("chosen_interface")
    host = data.get("hostname")

    # Basic validation - can be more extensive if needed here, though primarily in web_flask.py
    required_keys = ["ipv4_address", "ipv4_mask", "enabled_status", "chosen_interface", "hostname"]
    missing_keys = [key for key in required_keys if not data.get(key)]
    if missing_keys:
        msg = f"Missing required key(s) in configure_interface_request: {', '.join(missing_keys)}"
        logger.error(msg)
        return False, msg
    
    # Ensure description has a value if it was optional or allow empty
    if description is None: # Check if description was provided at all
        description = "None" # Default if not provided
        logger.debug(f"Description for {host}, interface {chosen_interface} was None, set to 'None'.")
    elif description == "":
        logger.debug(f"Description for {host}, interface {chosen_interface} is an empty string.")
        description = "None" # Or handle as per policy for empty strings

    is_valid, validation_error = is_valid_ip4(f"{ipv4}/{ipv4_mask}")
    if not is_valid:
        logger.error(f"Invalid IP/Mask for interface config on {host}: {ipv4}/{ipv4_mask}. Error: {validation_error}")
        return False, validation_error
    
    logger.info(f"Attempting to configure interface {chosen_interface} on host {host} with IP {ipv4}/{ipv4_mask}, Description: '{description}', Enabled: {enabled_status}")
    try:
        nr = get_nornir_runner_with_creds()
        nr_filtered = nr.filter(name=host)
        if not nr_filtered.inventory.hosts:
            logger.warning(f"Host '{host}' not found in inventory for interface configuration.")
            return False, f"Host '{host}' not found in inventory."
        
        result_agg = nr_filtered.run( 
            task=configure_interface, 
            chosen_interface=chosen_interface, 
            ip_address=ipv4, 
            ip_mask=ipv4_mask, 
            enabled_status=enabled_status, 
            description=description 
            )
        # print_result(result_agg) # Task-level logging is preferred
        
        if result_agg.failed:
            error_messages = []
            for failed_host_name in result_agg.failed_hosts: 
                host_result = result_agg[failed_host_name]
                # Try to get specific exception or result string
                exception_info = host_result.exception if hasattr(host_result, 'exception') else (host_result[0].exception if len(host_result) > 0 and hasattr(host_result[0], 'exception') else None)
                result_info = host_result[0].result if len(host_result) > 0 and hasattr(host_result[0], 'result') else "No specific result string"
                err_msg = f"Error on {failed_host_name}: {exception_info or result_info}"
                error_messages.append(err_msg)
            final_error_message = f"Configuration failed: {'; '.join(error_messages)}"
            exc_info_flag = any(hasattr(res, 'exception') and res.exception for res in result_agg.values())
            logger.error(f"Interface configuration task failed for host {host}. Details: {final_error_message}", exc_info=exc_info_flag)
            return False, final_error_message
        
        logger.info(f"Interface configuration request successful for host {host}, interface {chosen_interface}.")
        return True, "Interface configured successfully."

    except ValueError as ve: 
        logger.error(f"ValueError during interface configuration for host {host}: {str(ve)}", exc_info=True)
        return False, str(ve)
    except ConnectionError as ce: 
        logger.error(f"ConnectionError during interface configuration for host {host}: {str(ce)}", exc_info=True)
        return False, str(ce)
    except Exception as e:
        logger.error(f"Unexpected error during interface configuration for host {host}: {str(e)}", exc_info=True)
        return False, f"An unexpected error occurred: {str(e)}"

def get_bgp_configuration(host):
    logger.info(f"Getting BGP configuration for host: {host}")
    try:
        nr = get_nornir_runner_with_creds()
        nr_filtered = nr.filter(name=host)
        if not nr_filtered.inventory.hosts:
            logger.warning(f"Host '{host}' not found for BGP config.")
            raise ValueError(f"Host '{host}' not found in Nornir inventory for BGP config.")
        
        logger.debug(f"Running napalm_get 'get_config' for BGP on host {host}.")
        bgp_config_result = nr_filtered.run(task=napalm_get, getters=["get_config"])
        
        if bgp_config_result.failed:
            err_msg = bgp_config_result[host][0].result if host in bgp_config_result and bgp_config_result[host] else "NAPALM task 'get_config' failed without specific result."
            logger.error(f"Failed to get BGP configuration for {host}: {err_msg}")
            raise ConnectionError(f"Failed to get BGP configuration for {host}: {err_msg}")
        
        config_data = bgp_config_result[host][0].result.get("get_config", {})
        logger.info(f"Successfully retrieved BGP configuration for host: {host}")
        return config_data
    except ValueError as ve:
        logger.error(f"ValueError in get_bgp_configuration for {host}: {str(ve)}", exc_info=True)
        raise
    except ConnectionError as ce:
        logger.error(f"ConnectionError in get_bgp_configuration for {host}: {str(ce)}", exc_info=True)
        raise
    except Exception as e: 
        logger.error(f"Error in get_bgp_configuration for {host}: {str(e)}", exc_info=True)
        raise

def get_advertised_networks(host):
    logger.info(f"Getting advertised networks for host: {host}")
    temp_conf_file = None 
    try:
        full_config = get_bgp_configuration(host) 
        temp_conf_file = f"cisco_{host}_running_config.conf" 
        with open(temp_conf_file,'w') as f:
            f.write(full_config.get('running', '')) 
        logger.debug(f"Temporarily wrote running config for {host} to {temp_conf_file} for parsing.")
        
        parse = CiscoConfParse(temp_conf_file, syntax='ios')
        networks = []
        # Using a more general regex for router bgp <ASN>
        for network_obj in parse.find_objects_w_parents(r'^router bgp \d+',r'^\s*network '):
            networks.append(network_obj.text)
        
        logger.debug(f"Found advertised networks for {host}: {networks}")
        return networks
    except Exception as e:
        logger.error(f"Error getting advertised networks for {host}: {str(e)}", exc_info=True)
        raise 
    finally:
        if temp_conf_file and os.path.exists(temp_conf_file):
            try:
                os.remove(temp_conf_file)
                logger.debug(f"Removed temporary config file: {temp_conf_file}")
            except OSError as e:
                logger.error(f"Error removing temporary config file {temp_conf_file}: {str(e)}")


def parse_single_network(advertised_network_string):
    logger.debug(f"Parsing single network string: '{advertised_network_string}'")
    parts = advertised_network_string.strip().split()
    ipv4 = "0.0.0.0" 
    mask = "255.255.255.0" # Default assumption
    
    if "network" in parts:
        try:
            idx = parts.index("network")
            if len(parts) > idx + 1:
                ipv4 = parts[idx+1]
            if "mask" in parts:
                mask_idx = parts.index("mask")
                if len(parts) > mask_idx + 1:
                    mask = parts[mask_idx+1]
            # Basic validation for IP, specific mask logic might be needed if classful assumption is not okay
            is_ip_valid, _ = is_valid_ip4(ipv4) # from additional_functions
            is_mask_valid, _ = is_valid_ip4(mask) # Check if mask looks like an IP (basic check)
            if not is_ip_valid :
                logger.warning(f"Parsed IP '{ipv4}' from '{advertised_network_string}' is not valid. Defaulting IP.")
                ipv4 = "0.0.0.0" 
            if not is_mask_valid:
                 logger.warning(f"Parsed Mask '{mask}' from '{advertised_network_string}' is not valid. Defaulting mask.")
                 mask = "255.255.255.0"

        except ValueError: # Handle index() not found if "network" or "mask" is missing unexpectedly
            logger.warning(f"Could not properly parse network string due to missing keywords: '{advertised_network_string}'. Defaulting IP and Mask.")
            ipv4 = "0.0.0.0"
            mask = "255.255.255.0"
    else:
        logger.warning(f"Keyword 'network' not found in string: '{advertised_network_string}'. Defaulting IP and Mask.")

    logger.debug(f"Parsed network: IP={ipv4}, Mask={mask} from string '{advertised_network_string}'")
    return ipv4,mask

def get_parsed_advertised_networks(host):
    logger.info(f"Getting parsed advertised networks for host: {host}")
    try:
        networks = get_advertised_networks(host) 
        parsed_adv_networks = []
        for network_str in networks:
            ipv4, mask = parse_single_network(network_str) 
            if ipv4 != "0.0.0.0": 
                 parsed_adv_networks.append([ipv4, mask])
            else:
                 logger.warning(f"Skipping network string '{network_str}' for host {host} due to parsing returning default IP.")
        logger.info(f"Successfully parsed advertised networks for host {host}: {parsed_adv_networks}")
        return parsed_adv_networks
    except Exception as e: 
        logger.error(f"Error parsing advertised networks for {host}: {str(e)}", exc_info=True)
        raise 


def get_as_number(host):
    logger.info(f"Getting AS number for host: {host}")
    try:
        nr = get_nornir_runner_with_creds() # Use the centralized Nornir initializer
        if host not in nr.inventory.hosts:
            logger.warning(f"Host '{host}' not found in inventory when trying to get AS number.")
            return None # Or raise ValueError if AS is strictly required
        # Assuming as_number is stored in host.data directly or via host.get("as_number")
        as_number = nr.inventory.hosts[host].data.get("as_number") if nr.inventory.hosts[host].data else None
        if not as_number:
             logger.warning(f"AS number not found for host {host} in inventory data (host.data might be missing or 'as_number' key absent).")
        logger.info(f"AS number for host {host}: {as_number}")
        return as_number
    except ValueError as ve: # From get_nornir_runner_with_creds
        logger.error(f"ValueError getting AS number for {host}: {str(ve)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error getting AS number for {host}: {str(e)}", exc_info=True)
        raise # Re-raise other unexpected exceptions

def get_advertised_networks_info(host):
    logger.info(f"Getting advertised networks info (AS number and parsed networks) for host: {host}")
    try:
        # These functions now have their own comprehensive logging
        parsed_networks = get_parsed_advertised_networks(host) 
        as_number = get_as_number(host) 
        logger.info(f"Successfully retrieved advertised networks info for host {host}.")
        return as_number, parsed_networks
    except Exception as e:
        # Errors from underlying functions are already logged. Log context here and re-raise.
        logger.error(f"Error getting advertised networks info for {host}: {str(e)}", exc_info=True)
        raise

def edit_adv_networks_task(task,old_networks,new_networks,as_number):
    task_logger = logging.getLogger(f"nornir.task.{task.host.name}")
    task_logger.info(f"Starting 'edit_adv_networks_task' for AS {as_number} on {task.host.name}. Old: {old_networks}, New: {new_networks}")

    try:
        delete_diff, add_diff = generate_diff_lists(new_networks,old_networks)
        task_logger.debug(f"Networks to delete: {delete_diff}, Networks to add: {add_diff} for AS {as_number} on {task.host.name}")

        if not delete_diff and not add_diff:
            task_logger.info(f"No changes in advertised networks for BGP AS {as_number} on {task.host.name}.")
            # Return a Nornir Result for consistency, indicating no change.
            # Netmiko tasks usually return the config sent; here we return a message.
            return Result(host=task.host, result="No changes in advertised networks needed.", changed=False)


        adv_networks_bgp_config_template = task.run(
            task=template_file,
            template="advertised.j2",
            path="configuration/",
            as_number=as_number,
            add_diff=add_diff,
            delete_diff=delete_diff
        )
        adv_networks_bgp_config_output = adv_networks_bgp_config_template.result
        adv_networks_bgp_config_send = adv_networks_bgp_config_output.splitlines()
        task_logger.debug(f"Generated BGP config commands for AS {as_number} on {task.host.name}: {adv_networks_bgp_config_send}")

        send_config_result = task.run(task=netmiko_send_config, config_commands=adv_networks_bgp_config_send)

        if send_config_result.failed:
            task_logger.error(f"netmiko_send_config failed for BGP networks on AS {as_number}, host {task.host.name}. Error: {send_config_result.result}")
            # Nornir will propagate the failure.
        else:
            task_logger.info(f"Successfully edited advertised BGP networks for AS {as_number} on {task.host.name}.")
        # The result of send_config_result will be part of the aggregated results.
            
    except Exception as e:
        task_logger.error(f"Exception during 'edit_adv_networks_task' for AS {as_number} on {task.host.name}: {str(e)}", exc_info=True)
        raise # Propagate exception to Nornir framework

def edit_networks(form_data: dict):
    # Validate hostname
    host = form_data.get("hostname") # Use .get for safety
    logger.info(f"Received request to edit advertised networks for host: {host}. Form data (keys): {list(form_data.keys())}")

    if not host or not isinstance(host, str):
        msg = "Hostname is required and must be a non-empty string."
        logger.error(msg)
        return False, msg

    try:
        # Underlying functions (get_as_number, get_parsed_advertised_networks) already initialize Nornir and log.
        # They will raise exceptions if host not found or Nornir creds missing.
        as_number = get_as_number(host) 
        if not as_number: 
            # This condition implies AS number was not found in inventory data for a valid host,
            # or get_as_number returned None because host was not found (already logged by get_as_number).
            msg = f"Could not retrieve AS number for host '{host}'. Cannot edit networks. It might be missing in inventory data or host not found."
            logger.error(msg) 
            return False, msg

        old_networks = get_parsed_advertised_networks(host) # This also handles host not found or Nornir issues.
        logger.debug(f"Old networks for host {host} (AS {as_number}): {old_networks}")
        
        # Validate old networks - this is more of a sanity check as they come from the device.
        for ipv4, ipv4_mask in old_networks:
            is_valid, validation_error = is_valid_ip4(f"{ipv4}/{ipv4_mask}")
            if not is_valid:
                # This would indicate an issue with data fetched from device or parsing logic.
                msg = f"Invalid existing network format for {ipv4}/{ipv4_mask} on host {host} (AS {as_number}): {validation_error}"
                logger.error(msg)
                return False, msg # Fail fast if source data is problematic

        # Process and validate new networks from form_data
        new_networks_unvalidated = form_data_to_addr_mask_pairs(form_data) 
        logger.debug(f"New networks (unvalidated) from form for host {host} (AS {as_number}): {new_networks_unvalidated}")
        new_networks = []
        for ipv4, ipv4_mask in new_networks_unvalidated:
            is_valid, validation_error = is_valid_ip4(f"{ipv4}/{ipv4_mask}")
            if not is_valid:
                msg = f"Invalid new network format for {ipv4}/{ipv4_mask} from form data for host {host} (AS {as_number}): {validation_error}"
                logger.error(msg)
                return False, msg
            new_networks.append([ipv4, ipv4_mask])
        logger.debug(f"Validated new networks for host {host} (AS {as_number}): {new_networks}")
            
    except ValueError as ve: # From get_nornir_runner_with_creds in sub-functions or host not found
        logger.error(f"ValueError during initial data retrieval for editing networks on {host}: {str(ve)}", exc_info=True)
        return False, str(ve)
    except ConnectionError as ce: # From NAPALM getters in sub-functions
        logger.error(f"ConnectionError during initial data retrieval for editing networks on {host}: {str(ce)}", exc_info=True)
        return False, str(ce)
    except Exception as e: # Other unexpected errors
        logger.error(f"Unexpected error during initial data retrieval or validation for {host}: {str(e)}", exc_info=True)
        return False, f"Error during initial data retrieval or validation: {str(e)}"

    # This top-level try handles exceptions from the entire process of diffing and applying changes.
    # The previous SyntaxError was due to incorrect structuring here.
    try:
        delete_diff, add_diff = generate_diff_lists(new_networks, old_networks)
        logger.info(f"Network changes for host {host} (AS {as_number}) - To delete: {delete_diff}, To add: {add_diff}")

        result_summary_string = "The changes you've made:"
        if not delete_diff and not add_diff:
            result_summary_string = "No changes detected in advertised networks."
            logger.info(f"No network changes detected for host {host} (AS {as_number}).") # Added log for no changes
        else:
            for addr_mask_pair in delete_diff:
                result_summary_string += f"\n- {addr_mask_pair[0]}/{addr_mask_pair[1]}"
            if delete_diff and add_diff: 
                result_summary_string += "\n"
            for addr_mask_pair in add_diff:
                result_summary_string += f"\n+ {addr_mask_pair[0]}/{addr_mask_pair[1]}"
        
        logger.debug(f"Change summary string for host {host} (AS {as_number}): {result_summary_string}")

        if not delete_diff and not add_diff: # If no changes, no need to run Nornir task
            return True, result_summary_string

        # Initialize Nornir runner for the task execution phase
        nr_task_execution = get_nornir_runner_with_creds()
        nr_filtered_for_task = nr_task_execution.filter(name=host)

        if not nr_filtered_for_task.inventory.hosts:
            msg = f"Host '{host}' (AS {as_number}) became unavailable in inventory before applying network changes."
            logger.error(msg)
            return False, msg

        logger.info(f"Running 'edit_adv_networks_task' on host {host} (AS {as_number}).")
        result_agg = nr_filtered_for_task.run(
            task=edit_adv_networks_task, 
            old_networks=old_networks,   
            new_networks=new_networks,   
            as_number=as_number          
            )
    
        if result_agg.failed:
            error_messages = []
            for failed_host_name in result_agg.failed_hosts: 
                host_result = result_agg[failed_host_name]
                exception_info = host_result.exception if hasattr(host_result, 'exception') else (host_result[0].exception if len(host_result) > 0 and hasattr(host_result[0], 'exception') else None)
                result_info = host_result[0].result if len(host_result) > 0 and hasattr(host_result[0], 'result') else "No specific result string"
                err_msg = f"Error on {failed_host_name}: {exception_info or result_info}"
                error_messages.append(err_msg)
            final_error_message = f"Edit advertised networks failed: {'; '.join(error_messages)}"
            exc_info_flag = any(hasattr(res, 'exception') and res.exception for res in result_agg.values())
            logger.error(f"{final_error_message} for host {host} (AS {as_number}).", exc_info=exc_info_flag)
            return False, final_error_message
        
        logger.info(f"Successfully edited advertised networks for host {host} (AS {as_number}).")
        return True, result_summary_string

    except ValueError as ve: 
        logger.error(f"ValueError during Nornir task execution or diff generation for editing networks on {host} (AS {as_number}): {str(ve)}", exc_info=True)
        return False, str(ve)
    except Exception as e: # Catch any other unexpected error during this configuration phase
        logger.error(f"Unexpected error during network configuration task or diff generation for host {host} (AS {as_number}): {str(e)}", exc_info=True)
        return False, f"An unexpected error occurred during network configuration: {str(e)}"


# old_networks = [['172.168.32.0', '255.255.255.0'], ['172.168.33.0', '255.255.255.0'], ['172.168.34.0', '255.255.255.0']]
# new_networks = [['172.168.31.0', '255.255.255.0'], ['172.168.33.0', '255.255.255.0'], ['172.168.34.0', '255.255.255.0']]
# The previous code block was self-contained for the Nornir execution part.
# The initial try-except block for data retrieval and validation is separate and above this.
# The SyntaxError was specifically about a 'try' for diff generation not having its own 'except' or 'finally',
# or being improperly structured with the lines that followed it.
# The corrected structure ensures that the entire sequence from diff generation through Nornir execution
# is within a single try-except block, which is cleaner.

# nr = InitNornir(config_file="nornir_configuration/config.yaml")
# nr = nr.filter(name="R2")
# result = nr.run(
#             task=edit_adv_networks_task,
#             old_networks=old_networks,
#             new_networks=new_networks,
#             as_number="200"
#             )
# print_result(result)
# print(get_parsed_advertised_networks("R2"))
