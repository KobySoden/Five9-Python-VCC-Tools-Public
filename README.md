# Five9-Python-VCC-Tools

This library is used to automate various VCC configuration tasks as well as provide a template for others to create their own automations. This is designed for Five9 Employees. 

## SETUP
```bash
pip install -r requirements.txt
```
Update the example.env file and change its name to .env

## USAGE
```bash
python app.py --help
```
```text
Usage: app.py [OPTIONS] COMMAND [ARGS]...
Options:
  --verbose  Will print verbose messages.
  --debug    Will print debug messages.
  --help     Show this message and exit.

Commands:
  campaign      Provides configuration operations for campaigns
  ivr           Provides configuration operations for ivrs
  skill         Provides configuration operations for skills
  troubleshoot  Assists in domain troubleshooting
  whisper       Creates Whispers prompts and assigns them to skills
```

## USAGE EXAMPLES
### IVR 
1. Remove "Copy of" from module names in ivr scripts in a domain
```bash
python app.py ivr -c
```
2. Remove "Copy of" from module names in a specific ivr script 
```bash
python app.py ivr -c -n "YOURSCRIPTNAME"
```
### CAMPAIGN
examples coming soon
```bash
python app.py campaign --help
```
### SKILL 
```bash
python app.py campaign --help
```
### TROUBLESHOOT
1. Automates VCC portion of [this](https://fivn.sharepoint.com/sites/gts2/SitePages/Tracking-Agent-Audio-Issues.aspx) guide. 
```bash
python app.py troubleshoot --audio
```
