
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

@app.route("/interfaces", methods = ['POST', 'GET'])
def hosts_page():
    if request.method == 'GET':
        return f"The URL /host is accessed directly. Try going to '/hosts' to submit form"
    if request.method == 'POST':
        form_data = request.form
        hostname = form_data["chosen_host"]
        interfaces = list_host_interfaces_info(hostname)
        interfaces_ip = interfaces[1]
        interfaces_info = interfaces[0]
        return render_template("host.html",interfaces_ip=interfaces_ip,interfaces_info=interfaces_info,hostname=hostname)
        # return form_data

@app.route("/edit", methods = ['POST','GET'])
def edit():
    if request.method == 'GET':
        return f"The URL /host is accessed directly. Try going to '/hosts' to submit form"
    if request.method == 'POST':
        data = request.form
        result = configure_interface_request(data)
        return render_template("edit.html",data="Applied successfuly" if not result.failed else "Something failed")

