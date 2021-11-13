
from flask import Flask, render_template,request
from napalm import get_network_driver
import json
from main import get_config
from pprint import pprint
app = Flask(__name__,template_folder="templates")


#main page
@app.route("/")
def main_page():
    configuration = get_config("10.10.10.3","mea","cisco")
    return render_template("conf.html",conf=configuration)


