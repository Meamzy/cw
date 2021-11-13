from nornir import InitNornir
from nornir.core.inventory import Host
import nornir_napalm
from nornir_utils.plugins.functions import print_result, print_title
from nornir.core.task import Task as task
from nornir_jinja2.plugins.tasks import template_file, template_string
from nornir_netmiko.tasks import netmiko_send_config
from nornir_napalm.plugins.tasks import napalm_get




# def allocate_interface(task,interface_name: str,ip_address: str,ip_mask: str):
#     inteface_config = task.run(task=template_file,template="interface.j2",path="configuration/",
#     interface_name=interface_name,ip_address=ip_address,ip_mask=ip_mask)
#     inteface_config_output = inteface_config.result
#     inteface_config_send = inteface_config_output.splitlines()
#     task.run(task=netmiko_send_config,config_commands=inteface_config_send)

# print_title("Running the interfaces config")
# result = nr.run(task=allocate_interface,interface_name="FastEthernet3/0 ",ip_address="10.10.11.3",ip_mask="255.255.255.0")

def list_all_interfaces():
    # intefaces_info = nr.run(task=napalm_get, getters=["get_interfaces_ip"])
    # print(host.keys())
    nr = InitNornir(config_file="nornir_configuration/config.yaml")
    nr.inventory = nr.filter()
    # nr = nr.inventory.filter(host="R1")
    # intefaces_info = nr.run(task=napalm_get, getters=["get_interfaces_ip"])
    # print_result(intefaces_info)
    # print(intefaces_info0])

list_all_interfaces()
# print(dir(nornir_napalm.plugins))