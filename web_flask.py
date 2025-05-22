
"""
Main Flask application for the Network Automation Tool.

This module sets up the Flask web server, defines routes for user interaction,
handles user authentication, and interfaces with the `norn.py` module
for network device operations.
"""
import logging
import os # Added for FLASK_SECRET_KEY
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from napalm import get_network_driver
import json
from pprint import pprint
from norn import *

# --- Logging Setup ---
# Basic configuration for logging. This could be expanded (e.g., file rotation, different handlers)
logging.basicConfig(
    level=logging.INFO,  # Log INFO level and above (INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        # You might want to add logging.FileHandler("app.log") here for production
    ]
)
logger = logging.getLogger(__name__) # Logger for web_flask.py
# --- End Logging Setup ---

app = Flask(__name__, template_folder="templates")

# Configuration: Use environment variable for secret key if available, otherwise default.
# TODO: For production, ensure FLASK_SECRET_KEY is always set to a strong, unique value.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_very_secret_key_for_flask_sessions_dev_only')
if app.secret_key == 'your_very_secret_key_for_flask_sessions_dev_only':
    logger.warning("FLASK_SECRET_KEY environment variable not set. Using default development key. "
                   "This is insecure for production.")
app.config['SESSION_TYPE'] = 'filesystem'

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # The route for the login page

# In-memory user store (for demonstration purposes only).
# TODO: In a real application, replace this with a proper database-backed user store.
WEB_USERS = {
    "admin": {"password": "securepassword"}  # Example: admin/securepassword
}

class User(UserMixin):
    """Simple User class for Flask-Login."""
    def __init__(self, user_id):
        self.id = user_id

    @staticmethod
    def get(user_id):
        """Static method to retrieve a user by ID."""
        if user_id in WEB_USERS:
            return User(user_id)
        return None

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback."""
    logger.debug(f"Loading user: {user_id}")
    return User.get(user_id)
# --- End Flask-Login Setup ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        logger.info(f"User '{current_user.id}' already authenticated, redirecting to hosts page.")
        return redirect(url_for('hosts'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password') # Password itself is not logged for security.
        
        logger.info(f"Login attempt for username: '{username}'")

        user_entry = WEB_USERS.get(username)
        # Validate username and password
        if user_entry and user_entry['password'] == password:
            user = User(username)
            login_user(user) # Log in the user with Flask-Login
            logger.info(f"User '{username}' logged in successfully.")
            flash('Logged in successfully.', 'success')
            
            # Redirect to the page the user was trying to access, or default to 'hosts'
            next_page = request.args.get('next')
            logger.debug(f"Redirecting user '{username}' to: {next_page or url_for('hosts')}")
            return redirect(next_page or url_for('hosts'))
        else:
            logger.warning(f"Failed login attempt for username: '{username}'")
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Handles user logout."""
    user_id_before_logout = current_user.id
    logout_user()
    logger.info(f"User '{user_id_before_logout}' logged out successfully.")
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route("/")
@login_required 
def main_page():
    """
    Main landing page. Redirects authenticated users to the '/hosts' page.
    """
    logger.debug(f"User '{current_user.id}' accessed root, redirecting to /hosts.")
    return redirect(url_for('hosts')) 

@app.route('/hosts')
@login_required
def hosts():
    """Displays the list of manageable hosts."""
    logger.info(f"User '{current_user.id}' accessing /hosts page.")
    try:
        hosts_list = list_all_hosts() # Nornir creds from env are handled in norn.py
    except ValueError as e: # Specific Nornir credential errors
        logger.error(f"ValueError fetching host list for user '{current_user.id}': {str(e)}", exc_info=True)
        flash(str(e), 'danger') # Display the specific error to the user (e.g., missing env vars)
        return render_template("error.html", error_message=str(e))
    except Exception as e: # Catch any other unexpected errors during host listing
        logger.error(f"Unexpected exception fetching host list for user '{current_user.id}': {str(e)}", exc_info=True)
        flash(f"An unexpected error occurred while fetching hosts: {str(e)}", 'danger')
        return render_template("error.html", error_message=f"Could not retrieve host list: {str(e)}")
    
    if hosts_list is not None:
        logger.debug(f"Host list for user '{current_user.id}': {hosts_list}")
        session['host_list'] = hosts_list # Store host list in session for subsequent requests
    else:
        # This case should ideally not be reached if list_all_hosts raises an error on failure.
        logger.warning(f"Host list was None for user '{current_user.id}' when accessing /hosts (unexpected).")
        session['host_list'] = [] 

    return render_template(
        "hosts.html",
        hosts=hosts_list if hosts_list else [] # Pass empty list if None, for template safety
    )

@app.route("/advertised_networks", methods = ['POST', 'GET'])
@login_required
def advertised_networks_page():
    """
    Displays advertised BGP networks for a chosen host.
    Requires POST request with 'chosen_host'.
    """
    logger.info(f"User '{current_user.id}' accessing /advertised_networks (method: {request.method}).")
    if request.method == 'GET':
        logger.debug(f"GET request to /advertised_networks by user '{current_user.id}', redirecting to hosts.")
        flash("This page should be accessed via a POST request from the hosts page.", "info")
        return redirect(url_for('hosts'))
    
    # POST request processing
    if 'host_list' not in session:
        logger.warning(f"Session expired or host_list missing for user '{current_user.id}' in /advertised_networks.")
        flash("Session expired or host list not available. Please go back to Hosts page.", "warning")
        return redirect(url_for('hosts'))
    host_list_from_session = session["host_list"] # Use a more descriptive name
    
    form_data = request.form
    chosen_hostname = form_data.get("chosen_host") # More descriptive name
    logger.debug(f"User '{current_user.id}' selected host: '{chosen_hostname}' for advertised networks.")

    if not chosen_hostname:
        logger.warning(f"No 'chosen_host' in form data for /advertised_networks by user '{current_user.id}'.")
        flash("Missing 'chosen_host' in form data.", "danger")
        return redirect(url_for('hosts'))

    if chosen_hostname not in host_list_from_session:
        logger.warning(f"Invalid hostname '{chosen_hostname}' selected by user '{current_user.id}'. Not in session host_list.")
        flash(f"Invalid hostname: {chosen_hostname}. Please select a valid host from the list.", "danger")
        return redirect(url_for('hosts'))

    try:
        logger.info(f"Fetching advertised networks for host '{chosen_hostname}' by user '{current_user.id}'.")
        as_number, networks = get_advertised_networks_info(chosen_hostname)
        logger.info(f"Successfully fetched advertised networks for host '{chosen_hostname}'. AS: {as_number}, Networks: {networks}")
        return render_template(
            "advertised_networks.html",
            as_number=as_number, 
            networks=networks, 
            hostname=chosen_hostname, 
            host_list=host_list_from_session
        )
    except ValueError as ve: # Nornir credential or host not found errors from norn.py
        logger.error(f"ValueError for host '{chosen_hostname}' in /advertised_networks (User: '{current_user.id}'): {str(ve)}", exc_info=True)
        flash(str(ve), 'danger')
        return render_template("error.html", error_message=str(ve))
    except ConnectionError as ce: # NAPALM connection errors from norn.py
        logger.error(f"ConnectionError for host '{chosen_hostname}' in /advertised_networks (User: '{current_user.id}'): {str(ce)}", exc_info=True)
        flash(str(ce), 'danger')
        return render_template("error.html", error_message=str(ce))
    except Exception as e: # Other unexpected errors
        logger.error(f"Unexpected exception for host '{chosen_hostname}' in /advertised_networks (User: '{current_user.id}'): {str(e)}", exc_info=True)
        flash(f"An error occurred while fetching advertised networks for {chosen_hostname}. Details: {str(e)}", "danger")
        return render_template("error.html", error_message=f"Failed to get advertised networks for {chosen_hostname}: {str(e)}")

@app.route("/interfaces", methods = ['POST', 'GET'])
@login_required
def interfaces_page():
    """
    Displays interface information for a chosen host.
    Requires POST request with 'chosen_host'.
    """
    logger.info(f"User '{current_user.id}' accessing /interfaces (method: {request.method}).")
    if request.method == 'GET':
        logger.debug(f"GET request to /interfaces by user '{current_user.id}', redirecting to hosts.")
        flash("This page should be accessed via a POST request from the hosts page.", "info")
        return redirect(url_for('hosts'))

    # POST request processing
    if 'host_list' not in session:
        logger.warning(f"Session expired or host_list missing for user '{current_user.id}' in /interfaces.")
        flash("Session expired or host list not available. Please go back to Hosts page.", "warning")
        return redirect(url_for('hosts'))
    host_list_from_session = session["host_list"]

    form_data = request.form
    chosen_hostname = form_data.get("chosen_host")
    logger.debug(f"User '{current_user.id}' selected host: '{chosen_hostname}' for interfaces page.")

    if not chosen_hostname:
        logger.warning(f"No 'chosen_host' in form data for /interfaces by user '{current_user.id}'.")
        flash("Missing 'chosen_host' in form data.", "danger")
        return redirect(url_for('hosts'))

    if chosen_hostname not in host_list_from_session:
        logger.warning(f"Invalid hostname '{chosen_hostname}' selected by user '{current_user.id}' for /interfaces.")
        flash(f"Invalid hostname: {chosen_hostname}. Please select a valid host from the list.", "danger")
        return redirect(url_for('hosts'))
            
    try:
        logger.info(f"Fetching interface information for host '{chosen_hostname}' by user '{current_user.id}'.")
        # list_host_interfaces_info returns a tuple: (interfaces_info, interfaces_ip)
        interfaces_info, interfaces_ip = list_host_interfaces_info(chosen_hostname)
        logger.info(f"Successfully fetched interface information for host '{chosen_hostname}'.")
        return render_template(
            "interfaces.html",
            interfaces_ip=interfaces_ip,
            interfaces_info=interfaces_info,
            hostname=chosen_hostname,
            host_list=host_list_from_session
        )
    except ValueError as ve: # Nornir credential or host not found errors
        logger.error(f"ValueError for host '{chosen_hostname}' in /interfaces (User: '{current_user.id}'): {str(ve)}", exc_info=True)
        flash(str(ve), 'danger')
        return render_template("error.html", error_message=str(ve))
    except ConnectionError as ce: # NAPALM connection errors
        logger.error(f"ConnectionError for host '{chosen_hostname}' in /interfaces (User: '{current_user.id}'): {str(ce)}", exc_info=True)
        flash(str(ce), 'danger')
        return render_template("error.html", error_message=str(ce))
    except Exception as e: # Other unexpected errors
        logger.error(f"Unexpected exception for host '{chosen_hostname}' in /interfaces (User: '{current_user.id}'): {str(e)}", exc_info=True)
        flash(f"An error occurred while fetching interface information for {chosen_hostname}. Details: {str(e)}", "danger")
        return render_template("error.html", error_message=f"Failed to get interface information for {chosen_hostname}: {str(e)}")

@app.route("/editint", methods = ['POST','GET'])
@login_required
def editint():
    """Handles the submission of interface configuration changes."""
    logger.info(f"User '{current_user.id}' accessing /editint (method: {request.method}).")
    if request.method == 'GET':
        logger.debug(f"GET request to /editint by user '{current_user.id}', redirecting to hosts.")
        flash("This page should be accessed via a POST request from an interface editing form.", "info")
        return redirect(url_for('hosts')) 
    
    # POST request processing
    form_data = request.form
    # Log form data keys, not values, to avoid logging potentially sensitive info if form evolves.
    logger.debug(f"Form data keys for /editint by user '{current_user.id}': {list(form_data.keys())}")

    required_fields = ['hostname', 'chosen_interface', 'ipv4_address', 'ipv4_mask', 'enabled_status', 'description']
    missing_fields = [field for field in required_fields if not form_data.get(field)] # Check for empty or missing
    
    if missing_fields:
        logger.warning(f"Missing fields in /editint for user '{current_user.id}': {missing_fields}")
        flash(f"Missing required form fields: {', '.join(missing_fields)}", "danger")
        # Redirect back to the referring page if possible, otherwise to the main hosts page.
        return redirect(request.referrer or url_for('hosts'))

    # Extracted hostname for logging and redirection
    hostname_from_form = form_data.get('hostname')
    interface_from_form = form_data.get('chosen_interface')
    logger.info(f"User '{current_user.id}' attempting to configure interface for host '{hostname_from_form}', interface '{interface_from_form}'.")
    
    # configure_interface_request is in norn.py and handles Nornir interaction
    success, message = configure_interface_request(form_data) 
    
    if success:
        logger.info(f"Interface configuration successful for host '{hostname_from_form}' by user '{current_user.id}'. Message: {message}")
        flash(message, 'success')
    else:
        logger.error(f"Interface configuration failed for host '{hostname_from_form}' by user '{current_user.id}'. Message: {message}")
        flash(message, 'danger')
    
    # Redirect to the interfaces page for the specific host after attempting configuration.
    # This makes chosen_host a query parameter for the GET request to interfaces_page.
    # interfaces_page would need to handle 'chosen_host' as a POST field, so this redirect might need adjustment
    # if interfaces_page strictly expects POST for host selection.
    # For now, assuming interfaces_page can show a specific host if 'chosen_host' is passed,
    # or that it's okay to go back to the general host selection if not.
    # A better UX might be to redirect back to the specific interface editing form if possible.
    # The current redirect is to the interfaces list for that host (which is a POST route from 'hosts').
    # This redirect should ideally be a POST or interfaces_page should handle GET with chosen_host.
    # For simplicity, keeping the redirect to the interfaces_page (which expects POST for host selection)
    # This means the user might need to re-select the host.
    # A better redirect would be to the specific host's interface page, which requires a way to pass that.
    # Let's assume we redirect back to the referrer, which might be the interface edit page itself.
    return redirect(request.referrer or url_for('interfaces_page', chosen_host=hostname_from_form))


@app.route("/edit_advertised_networks", methods = ['POST','GET'])
@login_required
def edit_adv_networks():
    """Handles the submission of BGP advertised network changes."""
    logger.info(f"User '{current_user.id}' accessing /edit_advertised_networks (method: {request.method}).")
    if request.method == 'GET':
        logger.debug(f"GET request to /edit_advertised_networks by user '{current_user.id}', redirecting to hosts.")
        flash("This page should be accessed via a POST request from an advertised networks editing form.", "info")
        return redirect(url_for('hosts'))
    
    # POST request processing
    form_data = request.form
    # Log form data keys to avoid logging potentially large network lists.
    logger.debug(f"Form data keys for /edit_advertised_networks by user '{current_user.id}': {list(form_data.keys())}")

    hostname_from_form = form_data.get('hostname')
    if not hostname_from_form: # Ensure hostname is present
        logger.warning(f"Hostname missing in /edit_advertised_networks for user '{current_user.id}'.")
        flash("Hostname is missing in the form submission.", "danger")
        return redirect(url_for('hosts'))
    
    logger.info(f"User '{current_user.id}' attempting to edit advertised networks for host '{hostname_from_form}'.")
    # edit_networks is in norn.py and handles Nornir interaction
    success, message_or_data = edit_networks(form_data) 
    
    if success:
        logger.info(f"Edit advertised networks successful for host '{hostname_from_form}' by user '{current_user.id}'. Details: {message_or_data}")
        flash(message_or_data, 'success')
    else:
        logger.error(f"Edit advertised networks failed for host '{hostname_from_form}' by user '{current_user.id}'. Message: {message_or_data}")
        flash(message_or_data, 'danger')
    
    # Redirect to the advertised_networks page for the specific host.
    # Similar to /editint, this route expects POST for host selection.
    # Redirecting back to referrer might be a better user experience.
    return redirect(request.referrer or url_for('advertised_networks_page', chosen_host=hostname_from_form))

@app.route("/guide", methods = ['GET'])
@login_required 
def guide():
    """Displays the user guide page."""
    logger.info(f"User '{current_user.id}' accessed /guide.")
    return render_template("guide.html")

@app.route("/about", methods=["GET"])
@login_required 
def about():
    """Displays the about page."""
    logger.info(f"User '{current_user.id}' accessed /about.")
    return render_template("about.html")