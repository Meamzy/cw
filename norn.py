from nornir import InitNornir
from nornir.core.inventory import Host
import nornir_napalm
from nornir_utils.plugins.functions import print_result, print_title
from nornir.core.task import Result, Task as task
from nornir_jinja2.plugins.tasks import template_file, template_string
from nornir_netmiko.tasks import netmiko_send_config
from nornir_napalm.plugins.tasks import napalm_get
import json
import parser


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
    
def list_all_interfaces():
    nr = InitNornir(config_file="nornir_configuration/config.yaml")
    hosts = list_all_hosts()

    nr = nr.filter(name=hosts[0])
    intefaces_info = nr.run(task=napalm_get, getters=["get_interfaces"])
    print_result(intefaces_info)

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
    description = data["description"]
    ipv4 = data["ipv4_address"]
    ipv4_mask = data["ipv4_mask"]
    enabled_status = data["enabled_status"]
    chosen_interface = data["chosen_interface"]
    nr = InitNornir(config_file="nornir_configuration/config.yaml")
    result = nr.run(
        task=configure_interface,
        chosen_interface=chosen_interface,
        ip_address=ipv4,
        ip_mask=ipv4_mask,
        enabled_status=enabled_status,
        description=description
        )
    print_result(result)
    return result
    # def allocate_interface(task,interface_name: str,ip_address: str,ip_mask: str):
#     inteface_config = task.run(task=template_file,template="interface.j2",path="configuration/",
#     interface_name=interface_name,ip_address=ip_address,ip_mask=ip_mask)
#     inteface_config_output = inteface_config.result
#     inteface_config_send = inteface_config_output.splitlines()
#     task.run(task=netmiko_send_config,config_commands=inteface_config_send)
# print(type(list_host_interfaces_info('R1').result))
# list_all_interfaces()
# print(dir(nornir_napalm.plugins))

# list_all_interfaces()

# print(help(Result))

    
# list_info = list_host_interfaces_info("R1")
# with open("conf.json","w") as f:
#     f.write(json.dumps(list_info[1],indent=2))
# print(list_info[1]['FastEthernet0/0'])
# print(parser.parse_ip(list_info[1]))
