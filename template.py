""""
Author: Koby Soden
Date: 6/8/2023
Summary: Use this script to get started with VCC Automation Configuration

This script walks through an example of something that you might want to automate.
Each fundemental action that can be used to automat VCC configuration is covered in this script. 
These actions are:

1. Get Data From VCC Using API
2. Modify Data/Make Decisions Based On Data
3. Send Modified Data Back to VCC Using API
"""

import requests
import lxml.etree as etree
import xmltodict

###################### START API CONSTANTS ################################
url = "https://api.five9.com:443/wsadmin/v12/AdminWebService"
headers = {'Content-Type': 'application/xml', 'Authorization': 'Basic this is a placeholder Base64 encoded username and password'} #Copy this over from postman

###################### END API CONSTANTS ##################################
###################### START CODE TO GET IVR SCRIPTS ######################

#Get IVR Script Request body 
script = "Duplicates"
payload = f"<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:ser=\"http://service.admin.ws.five9.com/\">\r\n   <soapenv:Header/>\r\n   <soapenv:Body>\r\n      <ser:getIVRScripts>\r\n         <namePattern>{script}</namePattern>\r\n      </ser:getIVRScripts>\r\n   </soapenv:Body>\r\n</soapenv:Envelope>"

#Send API Request and store the response in a variable
response = requests.request("POST", url, headers=headers, data=payload)

#print(f"{response.text}")

#convert respnse xml to a dictionary to make access easier
response_dict = xmltodict.parse(response.text)

#Extract Raw IVR XML from the response
scriptDefinition = response_dict['env:Envelope']['env:Body']['ns2:getIVRScriptsResponse']['return']['xmlDefinition']
ivr_xml_root = etree.fromstring(scriptDefinition.encode('utf-8'))

#convert the ivr xml to a dictionary
ivr_dict = xmltodict.parse(scriptDefinition)

#USE ivr_xml_root to modify the xml (etree objects are better for sending back to the server) DONT ASK WHY :)

###################### END CODE TO GET IVR SCRIPTS ######################
###################### START COODE TO MODIFY XML ########################
print(f"\n----------------  These are the top level xml elements in an ivr script  --------------- \n")
for key in ivr_dict["ivrScript"].keys():
    print(key)
input("Press any key to continue...")

print(f"\n----------------  You can work with specific xml elements like this  ------------------- \n")
#choosing to look at the modules element here but you can choose any of the top level elements
target_element = ivr_xml_root.find('modules')
print(f"Element: {target_element.tag}")

input("Press any key to see the sub elements...")
#loop through all the sub elements of the target element
for sub_element in target_element:

    #this is where xml weirdness starts to come into play. The element name is a sub element called moduleName
    module_name = sub_element.find('moduleName')
    print(f"Name: {module_name.text} Type: {sub_element.tag} ")

    new_name = input("Enter a new name for the module or press enter: ")
    if new_name == "":
        continue
    else:
        #This is how you change the value of the element in the xml
        module_name.text = new_name 
###################### END CODE TO MODIFY XML ###########################
###################### START CODE TO UPDATE XML #########################

#convert the xml back to a string
modified_xml = etree.tostring(ivr_xml_root) #convert xml string so we can send it via api
modified_xml = modified_xml.replace(b'<', b'&lt;') #replace < with &lt; so that the xml is not interpreted as html
modified_xml = modified_xml.decode('utf-8') #convert bytes to string

print(f"\n----------------  Sending updated XML to the server  ------------------- \n")
payload = f"<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:ser=\"http://service.admin.ws.five9.com/\">\r\n   <soapenv:Header/>\r\n   <soapenv:Body>\r\n      <ser:modifyIVRScript>\r\n        <scriptDef>\r\n<name>{script}</name>\r\n<xmlDefinition>{modified_xml}</xmlDefinition>\r\n         </scriptDef>\r\n      </ser:modifyIVRScript>\r\n   </soapenv:Body>\r\n</soapenv:Envelope>"
response = requests.request("POST", url, headers=headers, data=payload)

print(f"{response.status_code} {response.reason}")

###################### END CODE TO UPDATE XML ###########################