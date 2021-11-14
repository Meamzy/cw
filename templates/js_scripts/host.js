var interfaces_info = {{ interfaces_info| tojson }};
var interfaces_ip = {{ interfaces_ip| tojson }}

function apply_check() {
    var ip_adress = document.getElementById("ipv4_address");
    var ip_mask = document.getElementById("ipv4_mask");
    if (ip_mask.value != null || ip_adress.value != null){
        ip_adress.setAttribute('required','required');
        ip_mask.setAttribute('required','required');
    }
    else {
    if(ip_adress.hasAttribute('required')) {
        ip_adress.removeAttribute('required')
    };
    if(ip_mask.hasAttribute('required')) {
        ip_mask.removeAttribute('required')
    };
    }
}

function edit_interface() {
    var ip_adress = document.getElementById("ipv4_address");
    var ip_mask = document.getElementById("ipv4_mask");
    var save_interface = document.getElementById("save_interface");
    var edit_button = document.getElementById("edit_button");

    if (save_interface.style.display === "none") {
        save_interface.style.display = "inline-block";
        edit_button.value = "Exit editing"
    } else {
        save_interface.style.display = "none";
        edit_button.value = "Edit interface"
    };

    if (description.hasAttribute('readonly')) {
        description.removeAttribute('readonly')
    } else {
        description.setAttribute('readonly', 'readonly');
    }
    if (ip_adress.hasAttribute('readonly')) {
        ip_adress.removeAttribute('readonly')
    } else {
        ip_adress.setAttribute('readonly', 'readonly');
    }
    if (ip_mask.hasAttribute('readonly')) {
        ip_mask.removeAttribute('readonly')
    } else {
        ip_mask.setAttribute('readonly', 'readonly');
    }
}
function createNetmaskAddr(bitCount) {
    var mask = [], i, n;
    for (i = 0; i < 4; i++) {
        n = Math.min(bitCount, 8);
        mask.push(256 - Math.pow(2, 8 - n));
        bitCount -= n;
    }
    return mask.join('.');
}
function select_interface_info() {

    document.getElementById("ipv4_address").setAttribute('readonly', 'readonly');
    document.getElementById("ipv4_mask").setAttribute('readonly', 'readonly');
    document.getElementById("description").setAttribute('readonly', 'readonly');
    document.getElementById("save_interface").style.display = "none";

    var interface_name = document.getElementById("chosen_interface").value;
    document.getElementById("interface_name").textContent = interface_name;
    document.getElementById("enabled_status").value = interfaces_info[interface_name]["is_enabled"];
    document.getElementById("up_status").textContent = interfaces_info[interface_name]["is_up"];
    document.getElementById("description").value = interfaces_info[interface_name]["description"];
    document.getElementById("mac_address").textContent = interfaces_info[interface_name]["mac_address"];
    document.getElementById("last_flapped").textContent = interfaces_info[interface_name]["last_flapped"];
    document.getElementById("mtu").textContent = interfaces_info[interface_name]["mtu"];
    document.getElementById("speed").textContent = interfaces_info[interface_name]["speed"];

    try {
        document.getElementById("ipv4_address").value = Object.keys(interfaces_ip[interface_name]["ipv4"]);
        document.getElementById("ipv4_mask").value = createNetmaskAddr(interfaces_ip[interface_name]["ipv4"][Object.keys(interfaces_ip[interface_name]["ipv4"])[0]]["prefix_length"]);
    } catch (error) {
        document.getElementById("ipv4_address").value = null
        document.getElementById("ipv4_mask").value = null
    };
};
function checkform() {
    document.getElementById("ipv4_address").value
    document.getElementById("ipv4_mask").value
}
