
from flask import Flask, render_template,request,session
from napalm import get_network_driver
import json
from pprint import pprint
from norn import *
app = Flask(__name__,template_folder="templates")

app.secret_key = 'super secret key'
app.config['SESSION_TYPE'] = 'filesystem'

#main page
@app.route("/")
def main_page():
    return "Hi ma men"

@app.route('/hosts')
def hosts():
    hosts_list = list_all_hosts()
    session['host_list'] = hosts_list
    return render_template(
        "hosts.html",
        hosts=hosts_list)


@app.route("/advertised_networks", methods = ['POST', 'GET'])
def advertised_networks_page():
    if request.method == 'GET':
        return f"The URL is accessed directly. Try going to '/hosts' to submit form"
    if request.method == 'POST':
        host_list = session["host_list"]
        form_data = request.form
        hostname = form_data["chosen_host"]
        as_number,networks = get_advertised_networks_info(hostname)
        return render_template(
            "advertised_networks.html",
            as_number = as_number, 
            networks = networks, hostname=hostname,host_list = host_list)

@app.route("/interfaces", methods = ['POST', 'GET'])
def interfaces_page():
    if request.method == 'GET':
        return f"The URL /host is accessed directly. Try going to '/hosts' to submit form"
    if request.method == 'POST':
        host_list = session["host_list"]
        form_data = request.form
        hostname = form_data["chosen_host"]
        interfaces = list_host_interfaces_info(hostname)
        interfaces_ip = interfaces[1]
        interfaces_info = interfaces[0]
        return render_template(
            "interfaces.html",
            interfaces_ip=interfaces_ip,
            interfaces_info=interfaces_info,
            hostname=hostname,
            host_list=host_list)

        # return form_data

@app.route("/editint", methods = ['POST','GET'])
def editint():
    if request.method == 'GET':
        return f"The URL /host is accessed directly. Try going to '/hosts' to submit form"
    if request.method == 'POST':
        data = request.form
        result = configure_interface_request(data)
        return render_template(
        "editint.html",
        data="Applied successfuly" if result[0] else f"Failed, the traceback:\n{result[1]}")

@app.route("/edit_advertised_networks", methods = ['POST','GET'])
def edit_adv_networks():
    if request.method == 'GET':
        return f"The URL /host is accessed directly. Try going to '/hosts' to submit form"
    if request.method == 'POST':
        return render_template("editnetworks.html", Data=edit_networks(request.form))

@app.route("/guide", methods = ['GET'])
def guide():
    if request.method == 'GET':
        return render_template(
        "guide.html",)

@app.route("/about", methods=["GET"])
def about():
    if request.method == 'GET':
        return render_template(
        "about.html",)