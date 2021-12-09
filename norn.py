from nornir import InitNornir
from nornir.core.inventory import Host
import nornir_napalm
from nornir_utils.plugins.functions import print_result, print_title
from nornir.core.task import Result, Task as task
from nornir_jinja2.plugins.tasks import template_file, template_string
from nornir_netmiko.tasks import netmiko_send_config
from nornir_napalm.plugins.tasks import napalm_get
import json
import os
from ciscoconfparse import CiscoConfParse
from additional_functions import is_valid_ip4,form_data_to_addr_mask_pairs,generate_diff_lists
# def allocate_interface(task,interface_name: str,ip_address: str,ip_mask: str):
#     inteface_config = task.run(task=template_file,template="interface.j2",path="configuration/",
#     interface_name=interface_name,ip_address=ip_address,ip_mask=ip_mask)
#     inteface_config_output = inteface_config.result
#     inteface_config_send = inteface_config_output.splitlines()
#     task.run(task=netmiko_send_config,config_commands=inteface_config_send)

# print_title("Running the interfaces config")
# result = nr.run(task=allocate_interface,interface_name="FastEthernet3/0 ",ip_address="10.10.11.3",ip_mask="255.255.255.0")

def list_all_hosts():
    nr = InitNornir(config_file="nornir_configuration/config.yaml")
    return list(nr.inventory.hosts.keys())

def list_host_interfaces_info(host:str):
    nr = InitNornir(config_file="nornir_configuration/config.yaml")
    nr = nr.filter(name=host)
    intefaces_info = nr.run(task=napalm_get, getters=["get_interfaces"])
    interfaces_ip = nr.run(task=napalm_get, getters=["get_interfaces_ip"])
    return (intefaces_info[host][0].result["get_interfaces"],interfaces_ip[host][0].result["get_interfaces_ip"])

def configure_interface(task,chosen_interface: str,ip_address: str,ip_mask: str,description: str, enabled_status):
    shut_no_shut = "no shut" if enabled_status=="true" else "shut"
    inteface_config = task.run(task=template_file,template="interface.j2",path="configuration/",
    chosen_interface=chosen_interface,
    ip_address=ip_address,
    ip_mask=ip_mask,
    description=description,
    shut_no_shut=shut_no_shut)
    inteface_config_output = inteface_config.result
    inteface_config_send = inteface_config_output.splitlines()
    task.run(task=netmiko_send_config,config_commands=inteface_config_send)
    
def configure_interface_request(data:dict):
    print(data)
    description = data["description"]
    ipv4 = data["ipv4_address"]
    ipv4_mask = data["ipv4_mask"]
    enabled_status = data["enabled_status"]
    chosen_interface = data["chosen_interface"]
    host = data["hostname"]
    if description=="" or description==None:
        description="None"
    is_valid,error = is_valid_ip4(f"{ipv4}/{ipv4_mask}")
    if is_valid:
        nr = InitNornir(config_file="nornir_configuration/config.yaml")
        nr = nr.filter(name=host)
        result = nr.run(
            task=configure_interface,
            chosen_interface=chosen_interface,
            ip_address=ipv4,
            ip_mask=ipv4_mask,
            enabled_status=enabled_status,
            description=description
            )
        print_result(result)
        return (True,error)
    else:
        return (False,error)

def get_bgp_configuration(host):
    nr = InitNornir(config_file="nornir_configuration/config.yaml")
    nr = nr.filter(name=host)
    bgp_config_info = nr.run(task=napalm_get, getters=["get_config"])
    return bgp_config_info[host][0].result["get_config"]

def get_advertised_networks(host):
    full_config = get_bgp_configuration(host)

    with open("cisco.conf",'w') as f:
        f.write(full_config['running'])
    parse = CiscoConfParse("cisco.conf", syntax='ios')
    networks = []
    for network in parse.find_objects_w_parents('^router bgp','^\s+network'):
        networks.append(network.text)
    os.remove("cisco.conf")
    return networks

def parse_single_network(advertised_network_string):
    advertised_network_string = advertised_network_string.strip().split()
    if len(advertised_network_string) == 4:
        network_keyword,ipv4,mask_keyword,mask = advertised_network_string
    else:
        network_keyword,ipv4 = advertised_network_string
        mask = "255.255.255.0"
    return ipv4,mask

def get_parsed_advertised_networks(host):
    networks = get_advertised_networks(host)
    parsed_adv_networks = []
    for network in networks:
        ipv4,mask = parse_single_network(network)
        parsed_adv_networks.append([ipv4,mask])
    return parsed_adv_networks

def get_as_number(host):
    nr = InitNornir(config_file="nornir_configuration/config.yaml")
    as_number = nr.inventory.hosts[host].get("as_number")
    return as_number

def get_advertised_networks_info(host):
    parsed_networks = get_parsed_advertised_networks(host)
    as_number = get_as_number(host)
    return as_number,parsed_networks

def edit_adv_networks_task(task,old_networks,new_networks,as_number):
    delete_diff, add_diff = generate_diff_lists(new_networks,old_networks)
    adv_networks_bgp_config = task.run(task=template_file,template="advertised.j2",path="configuration/",
    as_number=as_number,
    add_diff=add_diff,
    delete_diff=delete_diff)
    adv_networks_bgp_config_output = adv_networks_bgp_config.result
    adv_networks_bgp_config_send = adv_networks_bgp_config_output.splitlines()
    task.run(task=netmiko_send_config,config_commands=adv_networks_bgp_config_send)

def edit_networks(form_data):
    host = form_data["hostname"]
    as_number = get_as_number(host)
    old_networks = get_parsed_advertised_networks(host)
    new_networks = form_data_to_addr_mask_pairs(form_data)
    for ipv4,ipv4_mask in old_networks:
        if not is_valid_ip4(f"{ipv4}/{ipv4_mask}"): return is_valid_ip4(f"{ipv4}/{ipv4_mask}")
    for ipv4,ipv4_mask in new_networks:
        if not is_valid_ip4(f"{ipv4}/{ipv4_mask}"): return is_valid_ip4(f"{ipv4}/{ipv4_mask}")
    nr = InitNornir(config_file="nornir_configuration/config.yaml")

    delete_diff, add_diff = generate_diff_lists(new_networks,old_networks)

    result_string = """The changes you've made:"""
    for addr_mask_pair in delete_diff:
        result_string+= f"\n-{addr_mask_pair[0]}/{addr_mask_pair[1]}"
    result_string+="\n"
    for addr_mask_pair in add_diff:
        result_string+= f"\n+{addr_mask_pair[0]}/{addr_mask_pair[1]}"

    nr = nr.filter(name=host)
    result = nr.run(
            task=edit_adv_networks_task,
            old_networks=old_networks,
            new_networks=new_networks,
            as_number=as_number
            )
    
    print_result(result)
    
    return result_string

# old_networks = [['172.168.32.0', '255.255.255.0'], ['172.168.33.0', '255.255.255.0'], ['172.168.34.0', '255.255.255.0']]
# new_networks = [['172.168.31.0', '255.255.255.0'], ['172.168.33.0', '255.255.255.0'], ['172.168.34.0', '255.255.255.0']]

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
