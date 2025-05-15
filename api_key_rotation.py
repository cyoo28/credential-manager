#!/usr/bin/env python3
import sys
import os
import json
from datetime import datetime, timezone, timedelta
import argparse
import boto3

# Simple logger class (Don't need logging library for basic logging)
class Logger:
    # Init Arg:
    #   debug [bool] - set to True to print debugging statements
    def __init__(self, debug):
        self.debug = debug
    # Print statements if debug flag is set to True
    def print(self, msg):
        if self.debug:
            print(msg)

# Class to execute gcloud commands
class GCP:
    # Init Arg:
    #   projectId [str] - name of GCP project
    #   debug [bool] *opt - set to True to print debugging statements (default=False)
    def __init__(self, projectId, debug=False):
        self.projectId = projectId
        self.debugger = Logger(debug)
    # Execute gcloud command in format f"gcloud {command} --format='{format}' --project={self.projectId}"
    # Arg:
    #   command [str] - command for gcloud
    #   format [bool] *opt - output format for gcloud response (default=json)
    # Returns:
    #   gcloud api response
    def exec(self, command, format="json"):
        # Set up the gcloud command
        cmd = f"gcloud {command} --format='{format}' --project={self.projectId}"
        self.debugger.print(cmd)
        try:
            # Try to execute the command
            response = os.popen(cmd).read()
            return json.loads(response)
        except:
            return None
    # Execute custom gcloud command
    # Arg:
    #   command [str] - custom command to be executed
    # Returns:
    #   gcloud api response
    def custom_exec(self, command):
        try:
            # Try to execute the command
            response = os.popen(command).read()
            return json.loads(response)
        except:
            return None

# Class to manage secrets in GCP
class SecretManager:
    # Init Arg:
    #   projectId [str] - name of GCP project
    #   credMan [obj] - credential manager object to rotate credentials
    #   debug [bool] *opt - set to True to print debugging statements (default=False)
    #   test [bool] *opt - set to True to testing mode (default=False)
    def __init__(self, projectId, credMan, debug=False, test=False):
        self.projectId = projectId
        self.GCP = GCP(self.projectId, debug=debug)
        self.credMan = credMan
        self.debugger = Logger(debug)
        self.test = test
        self.rotatedSecrets = []
    # Get secrets in the project
    # Arg:
    #   limit [int] *opt - limit on how many secrets are returned (default=None)
    # Returns:
    #   secretsList [list of dict] - list of secrets
    def list_secrets(self, limit=None):
        # Initial command to list secrets
        cmd = "secrets list --sort-by=~createTime"
        # If limit flag is set, then add limit flag to limit returned versions
        if limit:
            cmd += f" --limit={limit}"
        # Get details for secret(s)
        secretsList = self.GCP.exec(cmd)
        self.debugger.print(secretsList)
        return secretsList
    # Get details for a secret
    # Arg:
    #   secretName [str] - name of secret 
    # Returns:
    #   secretDetails [dict] - details for the secret
    def describe_secret(self, secretName):
        # Get details for the secret
        secretDetails = self.GCP.exec(f"secrets describe {secretName}")
        self.debugger.print(secretDetails)
        return secretDetails
    # Get versions for a secret
    # Arg:
    #   secretName [str] - name of secret
    #   limit [int] *opt - limit on how many secrets are returned (default=None)
    #   enabled [bool] *opt - only return enabled versions (default=False)
    # Returns:
    #   versions [list of dict] - list of versions for the secret
    def list_versions(self, secretName, limit=None, enabled=False):
        # Initial command to list secrets
        # Sorted by creation time so newest are first
        cmd = f"secrets versions list {secretName} --sort-by=~createTime"
        # If limit flag is set, then add limit flag to limit returned versions
        if limit:
            cmd += f" --limit={limit}"
        # If enabled flag is set, then add enabled flag to list enabled versions only
        if enabled:
            cmd += f" --filter='state:ENABLED'"
        # Get versions for the secret
        versions = self.GCP.exec(cmd)
        if not versions:
            print("No versions available (check that there is at least 1 enabled version)")
        self.debugger.print(versions)
        return versions
    # Get annotations for a secret
    # Arg:
    #   secretName [str] - name of secret
    # Returns:
    #   annotations [dict] - annotations for the secret    
    def list_annotations(self, secretName):
        # Get annotations for the secret
        secretDetails = self.describe_secret(secretName)
        annotations = secretDetails.get("annotations", {})
        # There might not be any annotations for the secret
        if not annotations:
            print("No annotations available (check that the secret has annotations)")
        self.debugger.print(annotations)
        return annotations
    # Get latest version for a secret
    # Arg:
    #   secretName [str] - name of secret
    #   enabled [bool] *opt - only return enabled versions (default=True)
    # Returns:
    #   versions[0] [dict] - details for the latest version of the secret    
    def latest_version(self, secretName, enabled=True):
        # Get latest version info
        versions = self.list_versions(secretName, 1, enabled)
        return versions[0] if versions else None
    # Get latest annotation for a secret
    # Arg:
    #   secretName [str] - name of secret
    # Returns:
    #   latestAnnotation [dict] - latest annotation of the secret      
    def latest_annotation(self, secretName):
        # Get latest version info
        latestVersion = self.latest_version(secretName)
        # Get annotations for the secret
        annotations = self.list_annotations(secretName)
        if not latestVersion or not annotations:
            return {}
        # Get latest annotation
        latestKey = latestVersion.get("name").split("/")[-1]
        self.debugger.print(latestKey)
        latestValue = annotations.get(latestKey, None)
        if not latestValue:
            print("The latest version has no corresponding annotation")
        self.debugger.print(latestValue)        
        latestAnnotation = {latestKey: latestValue}
        return latestAnnotation if latestValue else {}
    # Check the type annotation for a secret
    # Arg:
    #   secretName [str] - name of secret
    # Returns:
    #   secretType [str] - secret type
    def check_type(self, secretName):
        # Get annotations
        annotations = self.list_annotations(secretName)
        # Extract secret type (if secret has the type annotation)
        secretType = annotations.get("type", None)
        return secretType
    # Enable a secret version
    # Arg:
    #   secretName [str] - name of secret
    #   version [int] - secret version
    def enable_version(self, secretName, version):
        # if in test mode, print action
        if self.test:
                print(f"'Enabled' version {version} for {secretName}")
        # otherwise, execute the enable command
        else:
            self.GCP.exec(f"secrets versions enable {version} --secret={secretName}")
    # Disable a secret version
    # Arg:
    #   secretName [str] - name of secret
    #   version [int] - secret version
    def disable_version(self, secretName, version):
        # if in test mode, print action
        if self.test:
                print(f"'Disabled' version {version} for {secretName}")
        # otherwise, execute the disable command
        else:
            self.GCP.exec(f"secrets versions disable {version} --secret={secretName}")
    # Add an annotation to a secret
    # Arg:
    #   secretName [str] - name of secret
    #   version [int] - secret version
    #   credId [str] - uid for the credential
    def add_annotation(self, secretName, version, credId):
        # Get annotations and add the new one
        annotations = self.list_annotations(secretName)
        annotations[f"{version}"] = credId
        annotationStr = ",".join([key+"="+value for key, value in annotations.items()])
        self.debugger.print(annotationStr)
        # if in test mode, print action
        if self.test:
            print(f"'Adding' annotation '{version}: {credId}' to {secretName}")
        # otherwise, execute the update annotations command
        else:
            self.GCP.exec(f"secrets update {secretName} --update-annotations='{annotationStr}'")
    # Add a version to a secret
    # Arg:
    #   secretName [str] - name of secret
    #   credId [str] - uid for the credential
    # Return:
    #   newVersionNum (int) - version number for the added version
    def add_version(self, secretName, credValue):
        # Custom command
        cmd = (
            f"echo -n {credValue} | gcloud secrets versions add {secretName} "
            f"--data-file=- --project={self.projectId} --format=json"
        )
        # If in test mode, print action,
        if self.test:
            print(f"'Adding' new credential '{credValue}' to {secretName}")
            newVersionNum = "NewVersion#"
        # Otherwise, execute custom command
        else:
            newVersionDetails = self.GCP.custom_exec(cmd)
            newVersionNum = newVersionDetails.get("name").split("/")[-1]
        return newVersionNum
    # Rotate secrets that are older than a specified number of days
    # Arg:
    #   expiryTime [int] - limit for how old secrets can be (in days)
    def rotate_secrets(self, expiryTime):
        # Get all secrets
        secrets = self.list_secrets()
        # There might not be any secrets in the project
        if not secrets:
            print("Error: There are no secrets in this project")
        for secret in secrets:
            secretName = secret.get("name").split("/")[-1]
            print(f"-----\nSecret Name: {secretName}")
            # Check that the secret is for an api key
            secretType = self.check_type(secretName)
            if not secretType=="api_key":
                print(f"{secretName} is not an api_key")
                continue
            # Check the latest version of the secret
            latestVersion = self.latest_version(secretName)
            if not latestVersion:
                print(f"Error: {secretName} has no versions")
                continue
            # Check the age of the secret
            print("Checking age of secret...")
            createDate = datetime.strptime(latestVersion.get("createTime"), "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            print(f"Creation Time: {createDate}")
            print(f" Current Time: {datetime.now(timezone.utc)}")
            # If the secret is older than the desired number of days
            if datetime.now(timezone.utc) - createDate > timedelta(days=expiryTime):
                # Get the latest annotation (which contains the associated key uid)
                latestAnnotation = self.latest_annotation(secretName)      
                if not latestAnnotation:
                    print(f"Error: {secretName} has no annotation corresponding to latest version")
                    continue
                print("Rotating key...")
                for oldVersionNum, oldKeyId in latestAnnotation.items():
                    # Rotate the key
                    displayName, newKeyId, newKeyString = self.credMan.rotate_key(oldKeyId)
                    print("Updating secret...")
                    # Disable the old secret version
                    self.disable_version(secretName, oldVersionNum)
                # Add the new secret version
                newVersionNum = self.add_version(secretName, newKeyString)
                # Add the new annotation for the new version
                self.add_annotation(secretName, newVersionNum, newKeyId)
            # Otherwise, don't rotate the secret
            else:
                print(f"{secretName} is not older than {expiryTime} day(s)")
                continue
            # Log the changes
            self.rotatedSecrets.append({"secretName": secretName, "oldVersion": oldVersionNum, "newVersion": newVersionNum, "keyName": displayName, "oldKeyId": oldKeyId, "newKeyId": newKeyId})

# Class to manage keys in GCP
class KeyManager:
    # Init Arg:
    #   projectId [str] - name of GCP project
    #   debug [bool] *opt - set to True to print debugging statements (default=False)
    #   test [bool] *opt - set to True to testing mode (default=False)
    def __init__(self, projectId, debug=False, test=False):
        self.projectId = projectId
        self.GCP = GCP(self.projectId, debug=debug)
        self.debugger = Logger(debug)
        self.test = test
    # Get keys in the project
    # Arg:
    #   limit [int] *opt - limit on how many secrets are returned (default=None)
    # Returns:
    #   keys [list of dict] - list of keys
    def list_keys(self, limit=None):
        # Initial command to list keys
        cmd = "services api-keys list --sort-by=~createTime"
        # If limit flag is set, then add limit flag to limit returned keys
        if limit:
            cmd += f"--limit={limit}"
        # Get details for key(s)
        keys = self.GCP.exec(cmd)
        self.debugger.print(keys)
        return keys
    # Get the string value for a key
    # Arg:
    #   keyId [str] - key uid
    # Return:
    #   keyString [str] - key string value
    def get_key_string(self, keyId):
        # Get the key string value
        keyString = self.GCP.exec(f"services api-keys get-key-string {keyId}").get("keyString")
        return keyString
    # Get the config for a key
    # Arg:
    #   keyId [str] - key uid
    # Return:
    #   keyConfig [dict] - key configuration
    def get_key_config(self, keyId):
        # Get the key config
        keyConfig = self.GCP.exec(f"services api-keys describe {keyId}")
        self.debugger.print(keyConfig)
        return keyConfig
    # Create a key
    # Arg:
    #   keyName [str] - key display name
    #   apiTargets *opt - api target restrictions (default=None)
    #   allowedIps *opt - ip restrictions (default=None)
    # Return:
    #   keyId [str] - key uId
    #   keyString [str] - key string value
    def create_key(self, keyName, apiTargets=None, allowedIps=None):
        # Initial command to create key
        cmd = f"gcloud services api-keys create --display-name='{keyName}' --format=json --project={self.projectId}"
        flags = []
        # If there are api targets, then add api-target flag(s) to add api targets
        if apiTargets:
            flags += [f"--api-target='{target}'" for target in apiTargets]
        # If there are allowed ips, then add allowed-ips flag to add allowed ips
        if allowedIps:
            flags.append(f"--allowed-ips='{allowedIps}'")
        self.debugger.print(flags)
        # Add flags to command
        cmd += " ".join(flags)
        # Move std.error to std.output (which has key string)
        cmd += " 2>1"
        # if in test mode, print action and return dummy key id and string
        if self.test:
            print(f"'Creating' new key with\n  apiTargets:{apiTargets}\n  allowedIps: {allowedIps}")
            keyId = "KeyIdFromKeyMan"
            keyString = "KeyStringFromKeyMan"
        # otherwise, execute key creation command
        else:
            keyId = self.GCP.custom_exec(cmd).get("response").get("uid")
            keyString = self.get_key_string(keyId)
        self.debugger.print(keyId)
        return keyId, keyString
    # Delete a key
    # Arg:
    #   keyId [str] - key uid
    def delete_key(self, keyId):
        # if in test mode, print action
        if self.test:
            print(f"'Deleting' key '{keyId}'")
        # otherwise, execute key deletion command
        else:
            self.GCP.exec(f"services api-keys delete {keyId}")

    # Rotate a key
    # Arg:
    #   oldKeyId [str] - old key uid
    # Returns:
    #   name - key display name
    #   newKeyId [str] - new key uid
    #   newKeyString [str] - new key string
    def rotate_key(self, oldKeyId):
        # Get old key configuration info
        keyInfo = self.get_key_config(oldKeyId)
        name = keyInfo.get("displayName")
        restrictions = keyInfo.get("restrictions", {})
        targets = restrictions.get("apiTargets", None)
        ips = restrictions.get("serverKeyRestrictions", {}).get("allowedIps", None)
        apiTargets = [f"{key}={value}" for target in targets for key, value in target.items()] if targets else None
        self.debugger.print(apiTargets)
        allowedIps = ",".join(ips) if ips else None
        self.debugger.print(allowedIps)
        # Create the new key
        newKeyId, newKeyString = self.create_key(name, apiTargets, allowedIps)
        # Delete the old key
        self.delete_key(oldKeyId)
        return name, newKeyId, newKeyString

# Send email notification with changed resources using AWS SES
# Arg:
#   sesClient [obj] - boto3 ses client instance
#   sender [str] - SES sender
#   recipients [list of str] - recipient email(s)
#   subject [str] - email subject
#   body [str] - email body
def send_email(sesClient, sender, recipients, subject, body):
    try:
        print("sending notification to: {}".format(recipients))
        charset = "UTF-8"
        res = sesClient.send_email(Destination={ "ToAddresses": recipients },
                                    Message={ "Body": { "Text": { "Charset": charset, "Data": body } },
                                              "Subject": { "Charset": charset, "Data": subject } },
                                    Source=sender)
        if "MessageId" in res:
            print("Notification sent successfully: {}".format(res["MessageId"]))
        else:
            print("Notification may not have been sent: {}".format(res))
    except Exception as e:
        print("Failed to send email: {}".format(e))

# Write changed resources to a file
# Arg:
#   sMan [obj] - secret manager instance
#   fileName [str] - output file name
def write_file(sMan, fileName):
    # Begin the file and write the headers
    with open(fileName, "w") as file:
        file.write("Secret Name, Old Secret Version, New Secret Version, Key Name, Old Key Id, New Key Id\n")
    # if no resources have been changed, report that
    if not sMan.rotatedSecrets:
        with open(fileName, "a") as file:
            file.write("No resources have been changed")
    # otherwise, report changed resources
    else:
        for secretInfo in sMan.rotatedSecrets:
            with open(fileName, "a") as file:
                file.write(f"{secretInfo['secretName']}")
                file.write(f", {secretInfo['oldVersion']}")
                file.write(f", {secretInfo['newVersion']}")
                file.write(f", {secretInfo['keyName']}")
                file.write(f", {secretInfo['oldKeyId']}")
                file.write(f", {secretInfo['newKeyId']}\n")

# Arg:
#   projectId [str] - name of GCP project
#   expiryTime [int] - limit for how old secrets can be (in days)
#   outputType [dict] - specifies output file name and sender/recipient(s) emails
#   profileName [str] - boto3 profile to send email (default=None)
#   regionName [str] - aws region to access secret (default=us-east-1)
#   secretName [str] - secret that contains service account key file (default=None)
#   debug [bool] *opt - set to True to print debugging statements (default=False)
#   test [bool] *opt - set to True to testing mode (default=False)
def main(projectId, expiryTime, outputType, profileName=None, regionName="us-east-1", secretName=None, debug=False, test=False):
    # Initialize the key and secret manager instances
    kMan = KeyManager(projectId, debug, test)
    sMan = SecretManager(projectId, kMan, debug, test)
    # Access secret for GCP service account for running in EC2 or ECS
    if profileName:
        session = boto3.Session(profile_name=profileName, region_name=regionName)
    else:
        session = boto3.Session(region_name=regionName)
    if secretName:
        smClient = session.client("secretsmanager")
        response = smClient.get_secret_value(SecretId=secretName)["SecretString"]
        # Write secret to a file
        fileName = "tmp.json"
        with open(fileName, "w") as f:
            f.write(response)
        # Authenticate with gcloud service account
        _ = os.popen(f"gcloud auth activate-service-account --key-file={fileName} --project 'ix-sandbox'; rm {fileName}").read()
    # Rotate any secrets that are older than the desired expiry time
    sMan.rotate_secrets(expiryTime)
    """
    # Revoke GCP credentials
    _ = os.popen(f"gcloud auth revoke").read()
    """
    # Write results to output file
    if outputType.get("fileName"):
        write_file(sMan, fileName)
    # Send email(s)
    if outputType.get("sender"):
        # set up ses client
        sesClient = session.client("ses")
        # get sender and recipient(s)
        sender = outputType.get("sender")
        if outputType.get("recipients"):
            recipients = outputType.get("recipients")
            # format subject and body of general email notification
            genSubject = "Rotated Secret and Key Information"
            genBody = json.dumps(sMan.rotatedSecrets, indent=2)
            # Send email notification through SES
            send_email(sesClient, sender, recipients, genSubject, genBody)
        # send individual email notifications to key owners
        if not test:
            for rotatedSecret in sMan.rotatedSecrets:
                annotations = sMan.list_annotations(rotatedSecret["secretName"])
                notify = annotations.get("notification")
                if notify:
                    indSubject = "Your Key has been Rotated"
                    indBody = json.dumps(rotatedSecret, indent=2)
                    # Send email notification through SES
                    send_email(sesClient, sender, [notify], indSubject, indBody)

if __name__ == "__main__":
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description="Use this script to rotate keys associated with old secrets")
    # Create arguments
    parser.add_argument("projectId", type=str, help="Google Cloud Project Id")
    parser.add_argument("expiryTime", type=int, help="Time in days after which secrets should be rotated")
    parser.add_argument("--fileName", dest="fileName", type=str, help="Name of your file (include .csv extension)")
    parser.add_argument("--profileName", dest="profileName", type=str, help="Profile to use for boto3")
    parser.add_argument("--regionName", dest="regionName", type=str, default='us-east-1', help="aws region to access secret (default='us-east-1')")
    parser.add_argument("--secretName", dest="secretName", type=str, help="Secret for GCP service account key info")
    parser.add_argument("--sender", dest="sender", type=str, help="SES sender to send notification")
    parser.add_argument("--recipients", dest="recipients", type=str, nargs='+', help="Recipient(s) to receive notification (e.g. 'abc@gmail.com' 'xyz@yahoo.com'")
    parser.add_argument("--debug", dest="debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--test", dest="test", action="store_true", help="Enable dry-run testing mode")
    # Parse the command-line arguments
    args = parser.parse_args(sys.argv[1:])
    projectId = args.projectId
    expiryTime = args.expiryTime
    fileName = args.fileName
    profileName = args.profileName
    regionName = args.regionName
    secretName = args.secretName
    sender = args.sender
    recipients = args.recipients
    debug = args.debug
    test = args.test
    # Set up output types
    outputType = {"fileName": fileName, "sender": sender, "recipients": recipients}
    # Pass arguments to the main function
    main(projectId, expiryTime, outputType, profileName, regionName, secretName, debug, test)