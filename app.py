"""
Author: Koby Soden 
Date: 3/30/2023
Purpose: This script is a template for all Five9 Python automation scripts. It contains all the necessary imports and constants to get started.
"""

import requests
import csv
import sys
import json
import os
import xml.etree.ElementTree as ET
import lxml.etree as etree
import xmltodict
from requests.auth import HTTPBasicAuth
from getpass import getpass
import click
from dotenv import load_dotenv

#Constants
URL_REST = "https://api.five9.com/restadmin/api/v1/domains" #This is the base URL for all REST API calls
URL_SOAP = "https://api.five9.com:443/wsadmin/v12/AdminWebService" #This is the base URL for all SOAP API calls
LOGGING = True
RESULTSMAX = 100

class Five9Campaign:
    def __init__(self, id, domain_id,  name, auth, type) -> None:
        self.id = id
        self.domain_id = domain_id
        self.name = name
        self.auth = auth
        self.type = type
        self.definition = None #TODO implement functionality to get campaign definition based on type

    def add_parameter(self, param, value):
        if not response_error_handler(self.get_inbound_campaign()):
            click.echo(f"Error: Problem Retrieving Campaign: {self.name}")
            return
        schedules = self.definition['ivrSchedule']
        
        if param in schedules['defaultScheduleEntry']['generalData']['scriptParameters']:
            click.echo(f"Error: Parameter {param} already exists")
        else:
            #TODO update script to support multiple data types
            schedules['defaultScheduleEntry']['generalData']['scriptParameters'].append({'name': param, 'value': {'type': 'STRING','secure':False, 'value': value}})
            self.definition['ivrSchedule'] = schedules
            

        if 'customScheduleEntries' in schedules:
            for schedule in schedules['customScheduleEntries']:
                schedule['generalData']['scriptParameters'].append({'name': param, 'value': {'type': 'STRING','secure':False, 'value': value}})
        
        #self.definition['ivrSchedule'] = schedules
        payload = {"ivrSchedule": schedules}
        if response_error_handler(self.update_campaign(json.dumps(payload))):
            click.echo(f"Success: added parameter {param} to {self.name}")
        else:
            click.echo(f"Error: Problem adding parameter {param} to {self.name}")
    
    def get_inbound_campaign(self):
        #TODO make api call
        url = f"{URL_REST}/{self.domain_id}/campaigns/inbound_campaigns/{self.id}"
        response = requests.request("GET", url, auth=self.auth)
        if response_error_handler(response):
            self.definition = json.loads(response.text)

        return response

    def get_outbound_campaign(self):
        #TODO make api call
        pass
    
    def update_campaign(self, payload):
        """Updates the campaign with the new json definition"""
        url = f"{URL_REST}/{self.domain_id}/campaigns/inbound_campaigns/{self.id}"
        response = requests.request("PUT", url, auth=self.auth, data=payload)
        response_error_handler(response) #TODO handle errors

        return response

class Five9Skill:
    def __init__(self, id, domain_id, name, auth) -> None:
        self.id = id
        self.domain_id = domain_id
        self.name = name
        self.auth = auth
        self.prompt_id = ""
        self.prompt_name = ""

    def get_prompt_name(self):
        self.prompt_name = 'Whisper ' + str(self.name)

    def get_prompt_id(self):
        url = f"{URL_REST}/{DOMAIN_ID}/prompts?fields=id,name&filter=name==\'{self.prompt_name}\'"
        response = requests.request("GET", url, auth=self.auth)

        if not response_error_handler(response):
            click.echo(f"Error: Problem Retrieving Prompt: {self.prompt_name}")
            return False
        
        obj = json.loads(response.text)

        #make sure a prompt was found
        if len(obj['entities']) > 0:
            self.prompt_id = obj['entities'][0]['id']
            return True
        else:
            click.echo(f"Error: Problem Retrieving Prompt: {self.prompt_name}")
            return False
    
    def assign_whisper_prompt(self):
        """Updates skill and assigns whisper prompt to it"""
        if self.prompt_id == "":
            return
        url = f"{URL_REST}/{DOMAIN_ID}/skills/{self.id}"
        payload = json.dumps({"whisperPrompt": {"id": self.prompt_id}})
        response = requests.request("PUT", url, auth=self.auth, data=payload)

        return response_error_handler(response)
    
    def set_routevm(self):
        url = f"{URL_REST}/{DOMAIN_ID}/skills/{self.id}"
        payload = json.dumps({
        "routeVoiceMails" : "true"
        })
        response = requests.request("PUT", url, auth=self.auth, data=payload)
        response_error_handler(response)
        print(f"Route VMs Code: {response.status_code}")

class Five9IVR:
    def __init__(self, auth, name):
        self.auth = auth
        self.name = name
    def add_variable(self, name, type, input=True, output=True, BACKUP=True):
        """Adds the variable specified to the ivr script"""
        response = self.getScript() #TODO handle errors if script is not found
        if not response_error_handler(response):
            click.echo(f"Error: Problem Retrieving Script: {self.name}")
            return
        
        #convert xml to dictionary
        data_dict = xmltodict.parse(response.text)
        ivrRoot = ET.fromstring(data_dict['env:Envelope']['env:Body']['ns2:getIVRScriptsResponse']['return']['xmlDefinition'], parser=ET.XMLParser(encoding="utf-8"))

        if BACKUP:
            #if the folder does not exist create it
            if not os.path.exists("IVR Backups"):
                os.mkdir("IVR Backups")
            with open(f"IVR Backups/{self.name}.xml", "w") as backup:
                backup.write(data_dict['env:Envelope']['env:Body']['ns2:getIVRScriptsResponse']['return']['xmlDefinition'])
            backup.close()

        for items in ivrRoot:
                if items.tag == 'userVariables':
                    xml_add_variable(items, name, type, input, output)
                    script = ET.tostring(ivrRoot)
                    script = script.replace(b'<', b'&lt;')

        #update ivr script
        response = self.modifyScript(script.decode('utf-8'))
        if not response_error_handler(response):
            click.echo(f"Error: Problem Updating Script: {self.name}")
            if LOGGING:
                #if the folder does not exist create it
                if not os.path.exists("Failed Updates"):
                    os.mkdir("Failed Updates")
                with open(f"Failed Updates/{self.name}.xml", "w") as failed:
                    failed.write(script.decode('utf-8'))
                failed.close()
            return
        return response
    
    def clean(self, BACKUP=False):
        self.handleDuplicateNames(BACKUP)

    def modifyScript(self, xml):
        """calls the modifyIVRScript api and returns the response"""
        payload = f"<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:ser=\"http://service.admin.ws.five9.com/\">\r\n   <soapenv:Header/>\r\n   <soapenv:Body>\r\n      <ser:modifyIVRScript>\r\n       <scriptDef>\r\n            <name>{self.name}</name>\r\n            <xmlDefinition>\r\n{xml}            \r\n            </xmlDefinition>\r\n         </scriptDef>\r\n      </ser:modifyIVRScript>\r\n   </soapenv:Body>\r\n</soapenv:Envelope>"
        response = requests.request("POST", URL_SOAP, auth=self.auth, data=payload)
        response.encoding = response.apparent_encoding # override encoding by real educated guess as provided by chardet

        return response

    def getScript(self):
        """calls the getIVRScripts api and returns the xml in the form of a string"""
        payload = f"<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:ser=\"http://service.admin.ws.five9.com/\">\r\n   <soapenv:Header/>\r\n   <soapenv:Body>\r\n      <ser:getIVRScripts>\r\n         <!--Optional:-->\r\n         <namePattern>{self.name}</namePattern>\r\n      </ser:getIVRScripts>\r\n   </soapenv:Body>\r\n</soapenv:Envelope>"
        #headers = {"Content-Type" :"application/xml", "Accept-Encoding": "gzip,deflate,br"}

        response = requests.request("POST", URL_SOAP, auth=self.auth, data=payload)
        #response.encoding = response.apparent_encoding # override encoding by real educated guess as provided by chardet
        return response

    def xmlToAPIString(self, element):
        """convert xml definition to string"""
        #output = ET.tostring(element)
        output = etree.tostring(element) #convert xml to bytes
        output = output.replace(b'<', b'&lt;') #replace < with &lt; so that the xml is not interpreted as html
        output = output.decode('utf-8') #convert bytes to string

        return output

    def handleDuplicateNames(self, BACKUP=False):
        """Handles duplicate names by appending a number to the end of the name"""
        frequency = {} #dictionary to keep track of how many times a name has been used
        response = self.getScript() #TODO handle errors if script is not found
        if not response_error_handler(response):
            click.echo(f"Error: Problem Retrieving Script: {self.name}")
            return
        
        #convert xml to dictionary
        data_dict = xmltodict.parse(response.text)
        scriptDefinition = data_dict['env:Envelope']['env:Body']['ns2:getIVRScriptsResponse']['return']['xmlDefinition']
        ivrRoot = etree.fromstring(scriptDefinition.encode('utf-8'))

        if BACKUP:
            #if the folder does not exist create it
            if not os.path.exists("IVR Backups"):
                os.mkdir("IVR Backups")
            with open(f"IVR Backups/{self.name}.xml", "w") as backup:
                backup.write(data_dict['env:Envelope']['env:Body']['ns2:getIVRScriptsResponse']['return']['xmlDefinition'])
            backup.close()
        
        #iterate through all the modules and remove "Copy of" from the name
        element = ivrRoot.find('modules')
        for module in element:
            name = module.find('moduleName')
            newName = name.text.replace("Copy of ", "")
            frequency[newName] = frequency[newName] + 1 if newName in frequency else 0
            if frequency[newName] > 0:
                newName = newName + " " + str(frequency[newName])
            name.text = newName
            if VERBOSE:
                click.echo(f"Changing {name.text} to {newName} Type: {module.tag} ")

        #convert xml back to string
        output = self.xmlToAPIString(ivrRoot)

        #update ivr script
        response = self.modifyScript(output)
        if not response_error_handler(response):
            click.echo(f"Error: Problem Updating Script: {self.name}")
            if LOGGING:
                #if the folder does not exist create it
                if not os.path.exists("Failed Updates"):
                    os.mkdir("Failed Updates")
                with open(f"Failed Updates/{self.name}.xml", "w") as failed:
                    failed.write(output)
                failed.close()
            return
        return response 

class Five9APIAgent:
    def __init__(self, username=None, password=None):
        if username == None and password == None:
            load_dotenv()
            username = os.environ.get("VCC-Username")
            password = os.environ.get("VCC-Password")
            if username == None and password == None:
                self.auth = get_auth()
            else:
                self.auth = HTTPBasicAuth(username, password)
        else:
            self.auth = HTTPBasicAuth(username, password)
        self.get_domain_id() #TODO add a loop to ensure that this can be collected 

    def get_partition_admin_username(self):
        payload={}
        url = f"{URL_REST}/{self.domain_id}/users?limit=100&filter=partitionAdminRole=isnull=false"
        response = requests.request("GET", url, auth=self.auth, data=payload)
        if response.status_code == 401:
            print("Error: Invalid credentials")
            return None
        elif response.status_code != 200:
            response_error_handler(response)
            return None
        else:
            partitionAdmin = json.loads(response.text)
        return partitionAdmin['entities'][0]['userName']
    
    def get_domain_id(self):
        #TODO Allow user to manually input domain id
        payload = "<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:ser=\"http://service.admin.ws.five9.com/\">\r\n   <soapenv:Header/>\r\n   <soapenv:Body>\r\n      <ser:getVCCConfiguration/>\r\n   </soapenv:Body>\r\n</soapenv:Envelope>"
        while True:    
            response = requests.request("POST", URL_SOAP, auth=self.auth, data=payload)
            if response_error_handler(response):
                break
            else:
                if DEBUG or VERBOSE:
                    click.echo(f"Error: One of the old APIs Failed. Trying again...")
                pass
        domain = xmltodict.parse(response.text)
        try:
            self.domain_id = domain['env:Envelope']['env:Body']['ns2:getVCCConfigurationResponse']['return']['domainId']
            self.domain_name = domain['env:Envelope']['env:Body']['ns2:getVCCConfigurationResponse']['return']['domainName']
        except KeyError:
            print(f"Problem Getting Domain ID: This is what was returned: {domain}")
            exit(1)
        return self.domain_id
    
    def get_campaigns(self, limit=RESULTSMAX, fields=None, sort=None, offset=0, order=None, filter=None):
        url = f"{URL_REST}/{self.domain_id}/campaigns"
        response = requests.request("GET", url, auth=self.auth, params={"limit": limit, "fields": fields, "sort": sort, "offset": offset, "order": order, "filter": filter})
        response_error_handler(response)
        campaigns = json.loads(response.text)
        return campaigns
    
    def get_skills(self, limit=RESULTSMAX, fields=None, sort=None, offset=0, order=None, filter=None):
        url = f"{URL_REST}/{self.domain_id}/skills"
        results = RESULTSMAX
        skills = []
        
        #hit api and get all the skills
        while results == RESULTSMAX:
            response = requests.request("GET", url, auth=self.auth, params={"limit": limit, "fields": fields, "sort": sort, "offset": offset, "order": order, "filter": filter})
            response_error_handler(response)
            full_response = json.loads(response.text)
            skills = skills + full_response['entities']
            results = int(full_response['resultsCount'])
            offset += RESULTSMAX
        
        #create Five9Skill objects
        output = []
        for skill in skills:
            output.append(Five9Skill(skill['id'], self.domain_id, skill['name'], self.auth))
        return output

    def get_ivrs(self, limit=RESULTSMAX, fields=None, sort=None, offset=0, order=None, filter=None):
        url = f"{URL_REST}/{self.domain_id}/scripts"
        results = RESULTSMAX
        ivrs = []
        while results == RESULTSMAX:
            response = requests.request("GET", url, auth=self.auth, params={"limit": limit, "fields": fields, "sort": sort, "offset": offset, "order": order, "filter": filter})
            response_error_handler(response)
            full_response = json.loads(response.text)
            ivrs = ivrs + full_response['entities']
            results = int(full_response['resultsCount'])
            offset += RESULTSMAX
        return ivrs
    
    def get_cav_id(self, name):
        url = f"{URL_REST}/{self.domain_id}/call-variables?filter=fullName==\"{name}\""
        response = requests.request("GET", url, auth=self.auth)
        if not response_error_handler(response):
            return None
        return json.loads(response.text)["entities"][0]["id"]
    
    def create_list(self, name):
        url = f"{URL_REST}/{self.domain_id}/call-lists"

        payload = json.dumps({"name": name, "kind": "CALL_LIST"})
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

        response = requests.request("POST", url, auth=self.auth, headers=headers, data=payload)
        response_error_handler(response)
        return response
    
    def create_contact_field(self, name,displayMode,dataType):
        url = f"{URL_REST}/{self.domain_id}/contact-fields"

        payload = json.dumps({"name": name,"type": "CUSTOM","displayMode": displayMode,
                                "dataType": dataType,"kind": "CONTACT_FIELD"})
        headers = {'Content-Type': 'application/json','Accept': 'application/json'}

        response = requests.request("POST", url, auth=self.auth, headers=headers, data=payload)
        response_error_handler(response)
        return response
    
#command line functionality
@click.group()
@click.option('--verbose', default=False, is_flag=True, help="Will print verbose messages.")
@click.option('--debug', default=False, is_flag=True, help="Will print debug messages.")
def cli(verbose, debug):
    """This tool is used to automate vcc configuration tasks"""
    global VERBOSE
    global DEBUG
    global DOMAIN_ID
    VERBOSE = verbose
    DEBUG = debug
    DOMAIN_ID = "me"

@cli.command()
@click.option('--username', type=click.STRING)
@click.option('--password', type=click.STRING)
@click.option('--name', "-n", type=click.STRING , help="The name of the target campaign", default=None)
@click.option('--parameter', '-p', type=click.STRING, help="The parameters to be passed to the campaign Format: \"name:value\"", default=None)
def campaign(username, password, name, parameter): #TODO implement functionality to interact with campaigns
    """Provides configuration operations for campaigns"""
    if username == None or password == None:
        agent=Five9APIAgent()
    else:
        agent = Five9APIAgent(username, password)
    DOMAIN_ID = agent.domain_id
    if name == None:
        objects = agent.get_campaigns()
    else:
        objects = agent.get_campaigns(filter=f"name==\'{name}\'")

    for object in objects["entities"]:
        click.echo(object['name'])
        campaign = Five9Campaign(object['id'], agent.domain_id, object['name'], agent.auth, type=object['type'])
        if parameter != None:
            if campaign.type != "INBOUND":
                click.echo(f"Error: Can't add parameter {campaign.name} is not an inbound campaign")
                continue
            param, value = parameter.split(":")
            campaign.add_parameter(param, value)


@cli.command() 
def skill(): #TODO implement functionality to interact with skills
    """Provides configuration operations for skills"""
    pass

@cli.command()
@click.option('--username', type=click.STRING)
@click.option('--password', type=click.STRING)
@click.option('--name', "-n", type=click.STRING , help="The name of the target script", default=None)
@click.option('--clean', "-c", default=False, is_flag=True, help="Removes \"Copy of \" from IVR module names")
@click.option('--backup', "-b", default=False, is_flag=True, help="Creates a backup of the IVR before any operations are performed")
@click.option('--addvariable', "-av", default=None, type=click.STRING, help="Adds a variable to the IVR script. Format: \"type:name\"")
def ivr(username, password, name, clean, backup, addvariable):
    """Provides configuration operations for ivrs"""
    #agent = auth(username, password)
    if username == None or password == None:
        agent=Five9APIAgent()
    else:
        agent = Five9APIAgent(username, password)
    DOMAIN_ID = agent.domain_id
    script = name
    if clean:
        if script == None:
            ivrs = agent.get_ivrs()
            for ivr in ivrs:
                if "owner" not in ivr.keys():
                    click.echo(f"Cleaning {ivr['name']}")
                    ivr = Five9IVR(agent.auth, ivr['name'])
                    ivr.clean(backup)
        else:
            click.echo(f"Cleaning {script}")
            ivr = Five9IVR(agent.auth, script)
            ivr.clean(backup)
    elif addvariable != None:
        type, name  = addvariable.split(":")
        if script == None:
            ivrs = agent.get_ivrs()
            for ivr in ivrs:
                if "owner" not in ivr.keys():
                    click.echo(f"Adding {name} to {ivr['name']}")
                    ivr = Five9IVR(agent.auth, ivr['name'])
                    ivr.add_variable(name, type)
        else:
            ivr = Five9IVR(agent.auth, script)
            click.echo(f"Adding {addvariable} to {script}")
            ivr.add_variable(name, type)

@cli.command()
@click.option('--audio', default=False, is_flag=True, help="Completes all the steps in this guide: https://fivn.sharepoint.com/sites/gts2/SitePages/Tracking-Agent-Audio-Issues.aspx")
@click.option('--username', type=click.STRING)
@click.option('--password', type=click.STRING)
def troubleshoot(username, password, audio):
    """Assists in domain troubleshooting"""
    if username == None or password == None:
        agent=Five9APIAgent()
    else:
        agent = Five9APIAgent(username, password)
    DOMAIN_ID = agent.domain_id
    if audio:
        click.echo("Configuring Domain")
        click.echo("Creating Quality Issues List")
        agent.create_list("Quality Issues")
        click.echo("Creating Contact Fields")
        agent.create_contact_field("Agent Name","HIDDEN","STRING")
        agent.create_contact_field("ANI","HIDDEN","STRING")
        agent.create_contact_field("DNIS","HIDDEN","STRING")
        agent.create_contact_field("Call_ID","HIDDEN","STRING")
        agent.create_contact_field("Session_ID","HIDDEN","STRING")
        agent.create_contact_field("Campaign","HIDDEN","STRING")
        agent.create_contact_field("Quality Issue","HIDDEN","STRING")
        agent.create_contact_field("Create_Date","HIDDEN","DATE_TIME")
        id_agent_name = agent.get_cav_id("Customer.Agent Name")
        id_ani = agent.get_cav_id("Call.ANI")
        id_dnis = agent.get_cav_id("Call.DNIS")
        id_call_id = agent.get_cav_id("Call.call_id")
        id_session_id = agent.get_cav_id("Call.session_id")
        id_campaign = agent.get_cav_id("Call.campaign_name")
        id_number1 = agent.get_cav_id("Customer.number1")
        click.echo("Creating Audio Issue Connectors")
        create_audio_issue_connector("Dead Air", agent, id_agent_name, id_ani, id_dnis, id_call_id, id_session_id, id_campaign, id_number1)
        create_audio_issue_connector("One Way Audio", agent, id_agent_name, id_ani, id_dnis, id_call_id, id_session_id, id_campaign, id_number1)
        create_audio_issue_connector("Dropped Call", agent, id_agent_name, id_ani, id_dnis, id_call_id, id_session_id, id_campaign, id_number1)
    else:
        click.echo("Please use a flag to specify which troubleshooting task you would like to perform")

@cli.command()
@click.option('--username', type=click.STRING)
@click.option('--password', type=click.STRING)
@click.option('--out', "-o", type=click.STRING , help="", default=None) #TODO update click type and allow user to specify output file
def whisper(username, password, out):
    """Creates Whispers prompts and assigns them to skills"""
    outfile = "whisper.csv"
    if username == None or password == None:
        agent=Five9APIAgent()
    else:
        agent = Five9APIAgent(username, password)
    DOMAIN_ID = agent.domain_id
    skills = agent.get_skills()
    fields = ['text','verbiage','description']
    #create whisper prompt csv
    with open(outfile, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(fields)

        for skill in skills:
            skill.get_prompt_name()
            row = [skill.prompt_name, skill.name, skill.prompt_name]
            csvwriter.writerow(row)
        
        csvfile.close()
    
    #upload prompts
    input(f"Press any key once you have uploaded {outfile} to the domain")

    #assign prompts to skills
    for skill in skills:
        if skill.get_prompt_id():
            if skill.assign_whisper_prompt():
                click.echo(f"Successfully assigned {skill.prompt_name} to {skill.name}")
            else:
                click.echo(f"Error: Problem assigning {skill.prompt_name} to {skill.name}")
        #skill.set_routevm()

#Helper functions 
def auth(username, password) -> Five9APIAgent:
    if username and password:
        agent = Five9APIAgent(username, password)
    else:
        exit(1)
    return agent

def get_auth():
    auth = HTTPBasicAuth(input("Username:"), getpass())
    return auth

def create_audio_issue_connector(name, agent : Five9APIAgent, id_agent_name, id_ani, id_dnis, id_call_id, id_session_id, id_campaign, id_number1):
    url = f"{URL_REST}/{agent.domain_id}/web-connectors"

    payload = json.dumps({"name": name,"description": "",
    "url": {"pathParams": [{"type": "CONSTANT", "value": "https://api.five9.com/web2campaign/AddToList"}],
        "queryParams": [
        {
            "name": "Agent Name",
            "values": [
            {"type": "CALL_VARIABLE","callVariableRef": {"name": "Customer.Agent Name","id": id_agent_name}}]
        },
        {"name": "Call_ID",
            "values": [{
                "type": "CALL_VARIABLE",
                "callVariableRef": {"name": "Call.call_id","id": id_call_id}
            }]
        },
        {"name": "Quality Issue",
            "values": [{"type": "CONSTANT","value": name}]
        },
        {"name": "Campaign",
            "values": [{
                "type": "CALL_VARIABLE",
                "callVariableRef": {"name": "Call.campaign_name","id": id_campaign}
            }]
        },
        {"name": "F9domain",
            "values": [{"type": "CONSTANT","value": agent.domain_name}]
        },
        {"name": "F9key",
            "values": [{"type": "CONSTANT", "value": "Call_ID"}]
        },
        {
            "name": "F9list",
            "values": [{"type": "CONSTANT", "value": "Quality Issues"}]
        }
        ]
    },
    "triggerDispositionRefs": [],
    "type": "CLASSIC",
    "method": "POST",
    "body": {
        "type": "FORM",
        "parameters": [
        {"name": "ANI",
            "values": [{"type": "CALL_VARIABLE","callVariableRef": {"name": "Call.ANI","id":id_ani}}]
        },
        {"name": "DNIS",
            "values": [{
                "type": "CALL_VARIABLE",
                "callVariableRef": {"name": "Call.DNIS", "id": id_dnis}
            }]
        },
        {"name": "number1",
            "values": [{
                "type": "CALL_VARIABLE",
                "callVariableRef": {"name": "Customer.number1","id": id_number1}
            }]
        },
        {"name": "Session_ID",
            "values": [{
                "type": "CALL_VARIABLE",
                "callVariableRef": {"name": "Call.session_id","id": id_session_id}
            }]
        }
        ],
        "addWorksheet": False
    },
    "startPageText": "Please wait while the connector is started",
    "triggerEvent": "ON_CALL_DISPOSITIONED",
    "executionMode": "SILENTLY",
    "browserAppType": "EMBEDDED_BROWSER",
    "browserWindowType": "CURRENT_BROWSER_WINDOW",
    "kind": "CONNECTOR"
    })
    headers = {'Content-Type': 'application/json','Accept': 'application/json'}

    response = requests.request("POST", url, auth=agent.auth, headers=headers, data=payload)
    response_error_handler(response)
    return response

def xml_add_variable(parent, name, type, input: bool, output: bool) -> ET.Element:
    """
    Adds script variable with type string to the script

    :param parent: userVariables element
    :param name: name of the variable being added
    :return: new xml element
    """
    #TODO add support for other variable types
    newEntry = xml_add_sub_element(parent, 'entry', '')
    xml_add_sub_element(newEntry, 'key', name)
    newValue = xml_add_sub_element(newEntry, 'value', '')
    xml_add_sub_element(newValue, 'name', name)
    xml_add_sub_element(newValue, 'description', '')
    if type == "str" or type == "string":
        newTypeValue = xml_add_sub_element(newValue, 'stringValue', '')
    elif type == "int" or type == "integer":
        newTypeValue = xml_add_sub_element(newValue, 'integerValue', '')
    


    xml_add_sub_element(newTypeValue, 'value', '')
    xml_add_sub_element(newTypeValue, 'id', '0')
    if input and output:
        xml_add_sub_element(newValue, 'attributes', '192')
    elif output:
        xml_add_sub_element(newValue, 'attributes', '128')
    elif input:
        xml_add_sub_element(newValue, 'attributes', '64')
    else:
        xml_add_sub_element(newValue, 'attributes', '8')
    xml_add_sub_element(newValue, 'isNullValue', 'true')
    return newEntry

def xml_add_sub_element(parent, tag, text) -> ET.Element:
	newElement = ET.SubElement(parent, tag)
	newElement.text = text
	return newElement

def response_error_handler(response) -> bool:
    """Returns true if the status code is 200, otherwise false"""
    if response.status_code == 200:
        return True
    elif response.status_code == 500:
        if DEBUG or VERBOSE: 
            click.echo(f"Error: Internal Server Error")
        return False
    elif response.status_code == 401:
        if DEBUG or VERBOSE:
            click.echo(f"Error: Invalid credentials ")
        return False
    else:
        if DEBUG or VERBOSE:
            click.echo(f"Error: {response.status_code} {response.reason}")
        return False

if __name__ == "__main__":
    cli()