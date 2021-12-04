
advertised_network_string = ' network 172.168.32.0 mask 255.255.255.0'
advertised_network_string = advertised_network_string.strip()
network_keyword,ipv4,mask_keyword,mask = advertised_network_string
return ipv4,mask