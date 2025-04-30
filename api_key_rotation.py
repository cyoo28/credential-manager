#!/usr/bin/env python3
import sys
import os
import json
from datetime import datetime, timezone, timedelta
import argparse

class Debugger:
    def __init__(self, debug):
        self.debug = debug
    def print(self, msg):
        if self.debug:
            print(msg)

class GCP:
    def __init__(self, projectId, debug=False):
        self.projectId = projectId
        self.debugger = Debugger(debug)
    def exec(self, command, format="json"):
        cmd = f"gcloud {command} --format='{format}' --project={self.projectId}"
        self.debugger.print(cmd)
        try:
            response = os.popen(cmd).read()
            return json.loads(response)
        except:
            return None
    def custom_exec(self, command):
        try:
            response = os.popen(command).read()
            return json.loads(response)
        except:
            return None

class SecretManager:
    def __init__(self, projectId, credManager, debug=False):
        self.projectId = projectId
        self.GCP = GCP(self.projectId, debug=debug)
        self.credManager = credManager
        self.debugger = Debugger(debug)
    def list_secrets(self, limit=None):
        cmd = "secrets list --sort-by=~createTime"
        if limit:
            cmd += f" --limit={limit}"
        secretsList = self.GCP.exec(cmd)
        self.debugger.print(secretsList)
        return secretsList
    def describe_secret(self, secretName):
        secretDetails = self.GCP.exec(f"secrets describe {secretName}")
        self.debugger.print(secretDetails)
        return secretDetails
    def list_versions(self, secretName, limit=None, enabled=False):
        cmd = f"secrets versions list {secretName} --sort-by=~createTime"
        if limit:
            cmd += f" --limit={limit}"
        if enabled:
            cmd += f" --filter='state:ENABLED'"
        versions = self.GCP.exec(cmd)
        if not versions:
            self.debugger.print("No versions available (check that there is at least 1 enabled version)")
        self.debugger.print(versions)
        return versions
    def list_annotations(self, secretName):
        secretDetails = self.describe_secret(secretName)
        annotations = secretDetails.get("annotations", {})
        if not annotations:
            self.debugger.print("No annotations available (check that the secret has annotations)")
        self.debugger.print(annotations)
        return annotations
    def latest_version(self, secretName):
        versions = self.list_versions(secretName, limit=1, enabled=True)
        return versions[0] if versions else None
    def latest_annotation(self, secretName):
        latestVersion = self.latest_version(secretName)
        annotations = self.list_annotations(secretName)
        if not latestVersion or not annotations:
            return {}
        latestNum = latestVersion.get("name").split("/")[-1]
        latestKey = f"version_{latestNum}"
        self.debugger.print(latestKey)
        latestValue = annotations.get(latestKey, None)
        if not latestValue:
            self.debugger.print("The latest version has no corresponding annotation")
        self.debugger.print(latestValue)        
        latestAnnotation = {latestKey: latestValue}
        return latestAnnotation if latestValue else {}
    def enable_version(self, secretName, version):
        self.GCP.exec(f"secrets versions enable {version} --secret={secretName}")
    def disable_version(self, secretName, version):
        self.GCP.exec(f"secrets versions disable {version} --secret={secretName}")
    def add_annotation(self, secretName, version, credId):
        annotations = self.list_annotations(secretName)
        annotations[f"version_{version}"] = credId
        self.debugger.print(annotations)
        annotationStr = ",".join([key+"="+value for key, value in annotations.items()])
        self.debugger.print(annotationStr)
        self.GCP.exec(f"secrets update {secretName} --update-annotations='{annotationStr}'")
    def add_version(self, secretName, credId, credValue):
        oldVersionDetails = self.latest_version(secretName)
        if oldVersionDetails:
            oldVersionNum = oldVersionDetails.get("name").split("/")[-1]
            self.disable_version(secretName, oldVersionNum)
        else:
            self.debugger.print("No older versions to disable")
        cmd = (
            f"echo -n {credValue} | gcloud secrets versions add {secretName} "
            f"--data-file=- --project={self.projectId} --format=json"
        )
        newVersionDetails = self.GCP.custom_exec(cmd)
        newVersionNum = newVersionDetails.get("name").split("/")[-1]
        self.add_annotation(secretName, newVersionNum, credId)

class KeyManager:
    def __init__(self, projectId, debug=False):
        self.projectId = projectId
        self.GCP = GCP(self.projectId, debug=debug)
        self.debugger = Debugger(debug)
    def list_keys(self, limit=None):
        cmd = "services api-keys list --sort-by=~createTime"
        if limit:
            cmd += f"--limit={limit}"
        keys = self.GCP.exec(cmd)
        self.debugger.print(keys)
        return keys
    def create_key(self, keyName, apiTargets=None, allowedIps=None):
        cmd = f"services api-keys create --display-name='{keyName}' "
        flags = []
        if apiTargets:
            flags += [f"--api-target='{target}'" for target in apiTargets]
        if allowedIps:
            flags.append(f"--allowed-ips='{allowedIps}'")
        self.debugger.print(flags)
        cmd += " ".join(flags)
        keyId = self.GCP.exec(cmd).get("response").get("uid")
        self.debugger.print(keyId)
        return keyId
    def delete_key(self, keyId):
        self.GCP.exec(f"services api-keys delete {keyId}")
    def get_key_string(self, keyId):
        keyString = self.GCP.exec(f"services api-keys get-key-string {keyId}").get("keyString")
        self.debugger.print(keyString)
        return keyString
    def get_key_config(self, keyId):
        keyConfig = self.GCP.exec(f"services api-keys describe {keyId}")
        self.debugger.print(keyConfig)
        return keyConfig
    def rotate_key(self, oldKeyId):
        keyInfo = self.get_key_config(oldKeyId)
        name = keyInfo.get("displayName")
        restrictions = keyInfo.get("restrictions", {})
        targets = restrictions.get("apiTargets", None)
        ips = restrictions.get("serverKeyRestrictions", {}).get("allowedIps", None)
        apiTargets = [f"{key}={value}" for target in targets for key, value in target.items()] if targets else None
        self.debugger.print(apiTargets)
        allowedIps = ",".join(ips) if ips else None
        self.debugger.print(allowedIps)
        newKeyId = self.create_key(name, apiTargets, allowedIps)
        newKeyString = self.get_key_string(newKeyId)
        self.delete_key(oldKeyId)
        return newKeyId, newKeyString

def checkSecret(sMan, secret, expiryTime):
    name = secret.get("name").split("/")[-1]
    print(f"Secret Name: {name}")
    latestVersion = sMan.latest_version(name)
    if not latestVersion:
        print(f"{name} has no versions")
        return name, {} 
    createDate = datetime.strptime(latestVersion.get("createTime"), "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    print(f"Creation Time: {createDate}")
    print(f"Current Time {datetime.now(timezone.utc)}")
    print(f"Is it older than {expiryTime} day(s)? {datetime.now(timezone.utc) - createDate > timedelta(days=expiryTime)}")
    if datetime.now(timezone.utc) - createDate > timedelta(days=expiryTime):
        latestAnnotation = sMan.latest_annotation(name)
        return name, latestAnnotation
    else:
        print(f"{name} is not older than {expiryTime} day(s)")
        return name, {}
    
def rotateKey(kMan, oldKeyId):
    print(f"Old Key Id: {oldKeyId}")
    newKeyId, newKeyString = kMan.rotate_key(oldKeyId)
    print(f"New Key Id: {newKeyId}")
    print(f"New Key String: {newKeyString}")
    newKey = ({newKeyId: newKeyString})
    return newKey

def updateSecret(sMan, secretName, key):
    print(f"Secret Name: {secretName}")
    for keyId, keyString in key.items():
        print(f"Key Id: {keyId}")
        print(f"Key String: {keyString}")
        sMan.add_version(secretName, keyId, keyString)

def main(projectId, expiryTime, debug=False):
    kMan = KeyManager(projectId, debug)
    sMan = SecretManager(projectId, kMan, debug)
    secrets = sMan.list_secrets()
    if not secrets:
        print("There are no secrets in this project")
    for secret in secrets:
        print(f"Checking if secret is old...")
        secretName, latestAnnotation = checkSecret(sMan, secret, expiryTime)
        if not latestAnnotation:
            print(f"This secret does not need to be rotated")
            continue
        for secretVersion, keyId in latestAnnotation.items():
            print(f"Rotating key...")
            newKey = rotateKey(kMan, keyId)
            print(f"Updating secret...")
            updateSecret(sMan, secretName, newKey)

if __name__ == "__main__":
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description="Use this script to rotate keys associated with old secrets")
    # Create arguments
    parser.add_argument("projectId", type=str, help="Google Cloud Project Id")
    parser.add_argument("expiryTime", type=int, help="Time in days after which secrets should be rotated")
    parser.add_argument("--debug", dest="debug", action="store_true", help="Enable debug mode")
    # Parse the command-line arguments
    args = parser.parse_args(sys.argv[1:])
    projectId = args.projectId
    expiryTime = args.expiryTime
    debug = args.debug

    main(projectId, expiryTime, debug)
