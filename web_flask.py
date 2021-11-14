
from flask import Flask, render_template,request
from napalm import get_network_driver
import json
from pprint import pprint
from norn import *
app = Flask(__name__,template_folder="templates")


#main page
@app.route("/")
def main_page():
    return "Hi ma men"

@app.route('/hosts')
def form():
    return render_template("hosts.html",hosts=list_all_hosts())

@app.route("/host", methods = ['POST', 'GET'])
def hosts_page():
    if request.method == 'GET':
        return f"The URL /host is accessed directly. Try going to '/hosts' to submit form"
    if request.method == 'POST':
        form_data = request.form
        hostname = form_data["chosen_host"]
        interfaces = list_host_interfaces_info(hostname)
        interfaces_ip = json.dumps(interfaces[1],indent=2)
        interfaces_info = json.dumps(interfaces[0],indent=2)
        return render_template("host.html",interfaces_ip=interfaces_ip,interfaces_info=interfaces_info,hostname=hostname)
        # return form_data
    

