from netmiko import ConnectHandler
import threading
import logging
import netmiko
import json
import mytools
import signal
import time
import paramiko
import socket
from datetime import datetime




logging.basicConfig(filename='../test.log', level=logging.DEBUG)
logger = logging.getLogger("netmiko")


signal.signal(signal.SIGPIPE, signal.SIG_DFL) #IOError : Broken pipe
signal.signal(signal.SIGINT, signal.SIG_DFL)#KeyboardInterrupt: Ctrl+C

netmiko_exceptions = (netmiko.ssh_exception.NetMikoTimeoutException,
					  netmiko.ssh_exception.NetMikoAuthenticationException,
					  netmiko.NetMikoTimeoutException
					  )


with open("../device.json",'r') as dev_file:
	devices = json.load(dev_file)

with open("../out.json",'r') as f:
	peers = json.load(f)

##############################################################
def pars(x):
	word = []
	inf = []
	lines = x.splitlines()
	word = [t.split() for t in lines]
	for i in word:
		if 'switchport' in i and 'allowed' in i:
			inf.append(i)
	return inf
#############################################################
def CheckInterface(x):
    lines = x.splitlines()[1:]
    interfaces = []
    for line in lines:
        words = line.split()[0:1]
        for i in words:
            if 'Gi' in i:
                interfaces.append(i)
    return interfaces
#############################################################
def CheckVtpServer(z):
    lines = z.splitlines()
    interfaces = []
    for line in lines:
        if "Operating" in line:
            interfaces.append(line)
    for line in interfaces:
        words = line.split()
    if "Server" in words:
        return "Server"
    else:
        return "Client"

###############################################################

threads_list = []
lock = threading.Lock()
device = {"ip":"","username":"","password":"","device_type":"","secret":""}
vlan_id = peers[0]["vlan"]
portValid = []
############################################################ configuration thread
def config(device1,input,output,vlan_id):
	try:
		device2 = {"ip":"","username":"","password":"","device_type":"","secret":""}
		device2 ['ip'] = device1["ip"]
		device2 ['username'] = device1 ["username"]
		device2 ['password'] = device1 ["password"]
		device2 ['secret'] = device1 ["secret"]
		device2 ['device_type'] = device1 ["device_type"]
		port1 = input
		port2 = output
		port = []
		vlanId = vlan_id
		connection = ConnectHandler(**device2)
		connection.enable()
		out1 = connection.send_command('show interfaces description')
		InterfaceInf = CheckInterface(out1)
		portValid = InterfaceInf
		port = [port1,port2]
		for i in port:
			if i in InterfaceInf:
				words = []
				output1 = connection.send_command('show running-config interface '+i)
				words = pars(output1)
				if len(words) == 0:
					config1 = ['interface '+i,'switchport trunk enc dot1q','switchport mode trunk','switchport trunk allowed vlan '+vlanId,'sp mode ra','sp vlan '+vlanId]
					sw_output = connection.send_config_set(config1)
				else:
					config1 = ['interface '+i,'switchport trunk enc dot1q','switchport mode trunk','switchport trunk allowed vlan add '+vlanId,'sp mode ra','sp vlan '+vlanId]
					sw_output = connection.send_config_set(config1)
			else:
				print("The interface {} is wrong.Please check the information again".format(i))
				print('~'*79)
				my_thread.do_run = False
				exit(1000)

		connection.enable()
		connection.send_command('write memory')
		connection.disconnect()
		print ('The connection to {} is disconnected'.format(device2['ip']))
		print('~'*79)

	except netmiko_exceptions as e:
		print('failed to ',device2['ip'],e)
		exit(3)

########################################################VTP server configuration

vlan_name = peers[0]["vlan_name"]
vtp = peers[0]["vtp"]
print('#'*60)
print('Connecting to VTP server to add the new vlan')
device ["ip"] = vtp
iplist = []
for l in devices:
	iplist.append(l["ip"])
if vtp in iplist:
	for i in devices:
		if i ["ip"] == vtp:
			device ['username'] = i ["username"]
			device ['password'] = i ["password"]
			device ['secret'] = i ["secret"]
			device ['device_type'] = "cisco_ios"

	vtp_connection = ConnectHandler(**device)
	vtp_connection.enable()
	out2 = vtp_connection.send_command('show vtp status')
	VTPStatus = CheckVtpServer(out2)
	if VTPStatus == "Server":
		vtp_config = ['vlan '+vlan_id,'name '+vlan_name,'no shutdown']
		vto_output = vtp_connection.send_config_set(vtp_config)
		print('Vtp server updating... ')
		vtp_connection.disconnect()
	else:
		print("The Selected VTP server is not actually a VTP Server,\
		It is in VTP Clinet mode...Leaving")
		exit(200)
else:
	print("There is No Such IP Adress in DATABASE As the VTP Server...leaving")
	exit(166)

############################################### Main function
start_time = datetime.now()
print(start_time)
print('~'*79)
ip_list=[]
for j in devices:
    ip_list.append(j["ip"])
for a_device in peers:
    ip = a_device['ip']
    input = a_device['port1']
    output = a_device['port2']
    print('Connecting to device',a_device['ip'])
    if ip in ip_list:
        for i in devices:
            if i["ip"] == ip:
                print("Fetching the information from the database for device: ",i["ip"])
                device ['ip'] = ip
                device ['username'] = i ["username"]
                device ['password'] = i ["password"]
                device ['secret'] = i ["secret"]
                device ['device_type'] = i ["device_type"]
                my_thread = threading.Thread(target=config, args= (device,input,output,vlan_id))
                threads_list.append(my_thread)
                my_thread.start()
    else:
        print("There is no Entry for {} in the database".format(ip))
        print('#'*40)
        exit(151)

main_thread = threading.currentThread()
for t in threads_list:
	if t != main_thread:
		t.join()

end_time = datetime.now()
print(end_time)
