import os
import json
from datetime import datetime, timezone, timedelta

class GCP:
    def __init__(self, projectId, debug=False):
        self.projectId = projectId
        self.debug = debug
    def debug_print(self, msg):
        if self.debug:
            print(msg)
    def exec(self, command, format="json"):
        cmd = f"gcloud {command} --format='{format}' --project={self.projectId}"
        self.debug_print(cmd)
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
        self.debug = debug
        self.GCP = GCP(self.projectId, debug=self.debug)
        self.credManager = credManager
    def debug_print(self, msg):
        if self.debug:
            print(msg)
    def list_secrets(self, limit=None):
        cmd = "secrets list --sort-by=~createTime"
        if limit:
            cmd += f" --limit={limit}"
        secretsList = self.GCP.exec(cmd)
        self.debug_print(secretsList)
        return secretsList
    def describe_secret(self, secretName):
        secretDetails = self.GCP.exec(f"secrets describe {secretName}")
        self.debug_print(secretDetails)
        return secretDetails
    def list_versions(self, secretName, limit=None, enabled=False):
        cmd = f"secrets versions list {secretName} --sort-by=~createTime"
        if limit:
            cmd += f" --limit={limit}"
        if enabled:
            cmd += f" --filter='state:ENABLED'"
        versions = self.GCP.exec(cmd)
        if not versions:
            self.debug_print("No versions available (check that there is at least 1 enabled version)")
        self.debug_print(versions)
        return versions
    def list_annotations(self, secretName):
        secretDetails = self.describe_secret(secretName)
        annotations = secretDetails.get("annotations", {})
        if not annotations:
            self.debug_print("No annotations available (check that the secret has annotations)")
        self.debug_print(annotations)
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
        self.debug_print(latestKey)
        latestValue = annotations.get(latestKey, None)
        if not latestValue:
            self.debug_print("The latest version has no corresponding annotation")
        self.debug_print(latestValue)        
        latestAnnotation = {latestKey: latestValue}
        return latestAnnotation if latestValue else {}
    def enable_version(self, secretName, version):
        self.GCP.exec(f"secrets versions enable {version} --secret={secretName}")
    def disable_version(self, secretName, version):
        self.GCP.exec(f"secrets versions disable {version} --secret={secretName}")
    def add_annotation(self, secretName, version, credId):
        annotations = self.list_annotations(secretName)
        annotations[f"version_{version}"] = credId
        self.debug_print(annotations)
        annotationStr = ",".join([key+"="+value for key, value in annotations.items()])
        self.debug_print(annotationStr)
        self.GCP.exec(f"secrets update {secretName} --update-annotations='{annotationStr}'")
    def add_version(self, secretName, credId, credValue):
        oldVersionDetails = self.latest_version(secretName)
        if oldVersionDetails:
            oldVersionNum = oldVersionDetails.get("name").split("/")[-1]
            self.disable_version(secretName, oldVersionNum)
        else:
            self.debug_print("No older versions to disable")
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
        self.debug = debug
        self.GCP = GCP(self.projectId, debug=self.debug)
    def debug_print(self, msg):
        if self.debug:
            print(msg)
    def list_keys(self, limit=None):
        cmd = "services api-keys list --sort-by=~createTime"
        if limit:
            cmd += f"--limit={limit}"
        keys = self.GCP.exec(cmd)
        self.debug_print(keys)
        return keys
    def create_key(self, keyName, apiTargets=None, allowedIps=None):
        cmd = f"services api-keys create --display-name='{keyName}' "
        flags = []
        if apiTargets:
            flags += [f"--api-target='{target}'" for target in apiTargets]
        if allowedIps:
            flags.append(f"--allowed-ips='{allowedIps}'")
        self.debug_print(flags)
        cmd += " ".join(flags)
        keyId = self.GCP.exec(cmd).get("response").get("uid")
        self.debug_print(keyId)
        return keyId    
    def delete_key(self, keyId):
        self.GCP.exec(f"services api-keys delete {keyId}")
    def get_key_string(self, keyId):
        keyString = self.GCP.exec(f"services api-keys get-key-string {keyId}").get("keyString")
        self.debug_print(keyString)
        return keyString
    def get_key_config(self, keyId):
        keyConfig = self.GCP.exec(f"services api-keys describe {keyId}")
        self.debug_print(keyConfig)
        return keyConfig
    def rotate_key(self, oldKeyId):
        keyInfo = self.get_key_config(oldKeyId)
        self.debug_print(keyInfo)
        name = keyInfo.get("displayName")
        restrictions = keyInfo.get("restrictions", {})
        targets = restrictions.get("apiTargets", None)
        ips = restrictions.get("serverKeyRestrictions", {}).get("allowedIps", None)
        apiTargets = [f"{key}={value}" for target in targets for key, value in target.items()] if targets else None
        self.debug_print(apiTargets)
        allowedIps = ",".join(ips) if ips else None
        self.debug_print(allowedIps)
        newKeyId = self.create_key(name, apiTargets, allowedIps)
        self.debug_print(newKeyId)
        newKeyString = self.get_key_string(newKeyId)
        self.debug_print(newKeyString)
        self.delete_key(oldKeyId)
        return newKeyId, newKeyString

def checkSecret(sMan, secret, expiryTime):
    name = secret.get("name").split("/")[-1]
    latestVersion = sMan.latest_version(name)
    createDate = datetime.strptime(latestVersion.get("createTime"), "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - createDate > timedelta(days=expiryTime):
        latestAnnotation = sMan.latest_annotation(name)
        return name, latestAnnotation
    else:
        return None
    
def rotateKey(kMan, oldKeyId):
    newKeyId, newKeyString = kMan.rotate_key(oldKeyId)
    newKey = ({newKeyId: newKeyString})
    return newKey

def updateSecret(sMan, secretName, key):
    for keyId, keyString in key.items():
        sMan.add_version(secretName, keyId, keyString)

def main(projectID, expiryTime, debug=False):
    kMan = KeyManager(projectID, debug)
    sMan = SecretManager(projectID, kMan, debug)
    secrets = sMan.list_secrets()
    if not secrets and debug:
        print("There are no secrets in this project")
    for secret in secrets:
        secretName, latestAnnotation = checkSecret(sMan, secret, expiryTime)
        for secretVersion, keyId in latestAnnotation.items():
            newKey = rotateKey(kMan, keyId)
            updateSecret(sMan, secretName, newKey)

if __name__ == "__main__":
    main(projectID, debug)