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

def list_all_hosts():
    nr = InitNornir(config_file="nornir_configuration/config.yaml")
    return list(nr.inventory.hosts.keys())

nr = InitNornir(config_file="nornir_configuration/config.yaml")
print(nr.inventory.hosts["R2"].get("as_number"))