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
    def __init__(self, projectId, credMan, debug=False, test=False):
        self.projectId = projectId
        self.GCP = GCP(self.projectId, debug=debug)
        self.credMan = credMan
        self.debugger = Debugger(debug)
        self.test = test
        self.rotatedSecrets = []
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
            print("No versions available (check that there is at least 1 enabled version)")
        self.debugger.print(versions)
        return versions
    def list_annotations(self, secretName):
        secretDetails = self.describe_secret(secretName)
        annotations = secretDetails.get("annotations", {})
        if not annotations:
            print("No annotations available (check that the secret has annotations)")
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
        latestKey = latestVersion.get("name").split("/")[-1]
        self.debugger.print(latestKey)
        latestValue = annotations.get(latestKey, None)
        if not latestValue:
            print("The latest version has no corresponding annotation")
        self.debugger.print(latestValue)        
        latestAnnotation = {latestKey: latestValue}
        return latestAnnotation if latestValue else {}
    def enable_version(self, secretName, version):
        if self.test:
                print(f"Enabled version {version} for {secretName}")
        else:
            self.GCP.exec(f"secrets versions enable {version} --secret={secretName}")
    def disable_version(self, secretName, version):
        if self.test:
                print(f"Disabled version {version} for {secretName}")
        else:
            self.GCP.exec(f"secrets versions disable {version} --secret={secretName}")
    def add_annotation(self, secretName, version, credId):
        annotations = self.list_annotations(secretName)
        annotations[f"{version}"] = credId
        annotationStr = ",".join([key+"="+value for key, value in annotations.items()])
        self.debugger.print(annotationStr)
        if self.test:
            print(f"Adding annotation '{version}: {credId}' to {secretName}")
        else:
            self.GCP.exec(f"secrets update {secretName} --update-annotations='{annotationStr}'")
    def add_version(self, secretName, credValue):
        cmd = (
            f"echo -n {credValue} | gcloud secrets versions add {secretName} "
            f"--data-file=- --project={self.projectId} --format=json"
        )
        if self.test:
            print(f"Adding new credential '{credValue}' to {secretName}")
            newVersionNum = "NewVersion#"
        else:
            newVersionDetails = self.GCP.custom_exec(cmd)
            newVersionNum = newVersionDetails.get("name").split("/")[-1]
        return newVersionNum
    def rotate_secrets(self, expiryTime):
        secrets = self.list_secrets()
        if not secrets:
            print("Error: There are no secrets in this project")
        for secret in secrets:
            secretName = secret.get("name").split("/")[-1]
            print(f"Secret Name: {secretName}")
            latestVersion = self.latest_version(secretName)
            if not latestVersion:
                print(f"Error: {secretName} has no versions")
                self.rotatedSecrets.append({secretName: "Error: No versions"})
                continue
            print("Checking age of secret...")
            createDate = datetime.strptime(latestVersion.get("createTime"), "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            self.debugger.print(f"Creation Time: {createDate}")
            self.debugger.print(f"Current Time {datetime.now(timezone.utc)}")
            if datetime.now(timezone.utc) - createDate > timedelta(days=expiryTime):
                latestAnnotation = self.latest_annotation(secretName)      
                if not latestAnnotation:
                    print(f"Error: {secretName} has no annotation corresponding to latest version")
                    self.rotatedSecrets.append({secretName: f"Error: Missing annotation"})
                    continue
                print("Rotating key...")
                for oldVersionNum, oldKeyId in latestAnnotation.items():
                    newKeyId, newKeyString = self.credMan.rotate_key(oldKeyId)
                    print("Updating secret...")
                    self.disable_version(secretName, oldVersionNum)
                newVersionNum = self.add_version(secretName, newKeyString)
                self.add_annotation(secretName, newVersionNum, newKeyId)
                self.rotatedSecrets.append({secretName: {oldVersionNum: oldKeyId, newVersionNum: newKeyId}})
            else:
                print(f"{secretName} is not older than {expiryTime} day(s)")
                self.rotatedSecrets.append({secretName: f"Less than {expiryTime} days old"})
                continue

class KeyManager:
    def __init__(self, projectId, debug=False, test=False):
        self.projectId = projectId
        self.GCP = GCP(self.projectId, debug=debug)
        self.debugger = Debugger(debug)
        self.test = test
        self.rotatedKeys = []
    def list_keys(self, limit=None):
        cmd = "services api-keys list --sort-by=~createTime"
        if limit:
            cmd += f"--limit={limit}"
        keys = self.GCP.exec(cmd)
        self.debugger.print(keys)
        return keys
    def get_key_string(self, keyId):
        keyString = self.GCP.exec(f"services api-keys get-key-string {keyId}").get("keyString")
        self.debugger.print(keyString)
        return keyString
    def get_key_config(self, keyId):
        keyConfig = self.GCP.exec(f"services api-keys describe {keyId}")
        self.debugger.print(keyConfig)
        return keyConfig
    def create_key(self, keyName, apiTargets=None, allowedIps=None):
        cmd = f"services api-keys create --display-name='{keyName}' "
        flags = []
        if apiTargets:
            flags += [f"--api-target='{target}'" for target in apiTargets]
        if allowedIps:
            flags.append(f"--allowed-ips='{allowedIps}'")
        self.debugger.print(flags)
        cmd += " ".join(flags)
        if self.test:
            print(f"Creating new key with\n  apiTargets:{apiTargets}\n  allowedIps: {allowedIps}")
            keyId = "KeyIdFromKeyMan"
            keyString = "KeyStringFromKeyMan"
        else:
            keyId = self.GCP.exec(cmd).get("response").get("uid")
            keyString = self.get_key_string(keyId)
        self.debugger.print(keyId)
        return keyId, keyString
    def delete_key(self, keyId):
        if self.test:
            print(f"Deleting key '{keyId}'")
        else:
            self.GCP.exec(f"services api-keys delete {keyId}")
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
        newKeyId, newKeyString = self.create_key(name, apiTargets, allowedIps)
        self.delete_key(oldKeyId)
        self.rotatedKeys.append({"old": oldKeyId,"new": newKeyId})
        return newKeyId, newKeyString

def main(projectId, expiryTime, debug=False, test=False):
    kMan = KeyManager(projectId, debug, test)
    sMan = SecretManager(projectId, kMan, debug, test)
    sMan.rotate_secrets(expiryTime)

if __name__ == "__main__":
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description="Use this script to rotate keys associated with old secrets")
    # Create arguments
    parser.add_argument("projectId", type=str, help="Google Cloud Project Id")
    parser.add_argument("expiryTime", type=int, help="Time in days after which secrets should be rotated")
    parser.add_argument("--debug", dest="debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--test", dest="test", action="store_true", help="Enable dry-run testing mode")
    # Parse the command-line arguments
    args = parser.parse_args(sys.argv[1:])
    projectId = args.projectId
    expiryTime = args.expiryTime
    debug = args.debug
    test = args.test
    # Pass arguments to the main function
    main(projectId, expiryTime, debug, test)
