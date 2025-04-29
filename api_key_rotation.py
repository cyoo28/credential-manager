import os
import json
from datetime import datetime, timedelta

class GCP:
    def __init__(self, projectId):
        self.projectId = projectId
    def exec(self, command, format="json"):
        cmd = "gcloud {} --format='{}' --project={}".format(command, format, self.projectId)
        print(cmd)
        response = os.popen(cmd)
        try:
            return json.loads(response.read())
        except:
            return None
    def custom_exec(self, command):
        response = os.popen(command)
        return json.loads(response.read())
    
class SecretManager:
    def __init__(self, projectId, credManager):
        self.projectId = projectId
        self.GCP = GCP(self.projectId)
        self.credManager = credManager
    def list_secrets(self, limit=None):
        if not limit:
            secretsList = self.GCP.exec("secrets list --sort-by=~createTime")
        else:
            secretsList = self.GCP.exec("secrets list --limit={} --sort-by=~createTime".format(limit))
        return secretsList
    def describe_secret(self, secretName):
        secretDetails = self.GCP.exec("secrets describe {}".format(secretName))
        return secretDetails
    def list_versions(self, secretName, limit=None):
        if not limit:
            versions = self.GCP.exec("secrets versions list {} --sort-by=~createTime".format(secretName))
        else:
            versions = self.GCP.exec("secrets versions list {} --limit={} --sort-by=~createTime".format(secretName, limit))
        return versions
    def list_annotations(self, secretName):
        secretDetails = self.describe_secret(secretName)
        annotations = secretDetails.get('annotations')
        return annotations
    def latest_version(self, secretName):
        latestVersion = self.list_versions(secretName, 1)[0]
        return latestVersion
    def latest_annotation(self, secretName):
        latestVersion = self.latest_version(secretName)
        latestVersionNum = latestVersion.get('name').split("/")[-1]
        annotations = self.list_annotations(secretName)
        latestKey = "version_{}".format(latestVersionNum)
        latestValue = annotations[latestKey]
        latestAnnotation = {latestKey: latestValue}
        return latestAnnotation
    def enable_version(self, version, secretName):
        self.GCP.exec("secrets versions enable {} --secret={}".format(version, secretName))
    def disable_version(self, version, secretName):
        self.GCP.exec("secrets versions disable {} --secret={}".format(version, secretName))
    def add_annotation(self, keyId, version, secretName):
        annotations = self.list_annotations(secretName)
        annotations["version_{}".format(version)] = keyId
        self.GCP.exec("secrets update {} --update-annotations='{}'".format(secretName, ",".join([key+"="+value for key, value in annotations.items()])))
    def add_version(self, keyId, secretValue, secretName):
        versionDetails = self.GCP.custom_exec("echo -n {} | gcloud secrets versions add {} --data-file=- --project={} --format=json".format(secretValue, secretName, self.projectID))
        version = versionDetails.get('name').split("/")[-1]
        self.add_annotation(keyId, version, secretName)

class KeyManager:
    def __init__(self, projectId):
        self.projectId = projectId
        self.GCP = GCP(self.projectId)
    def list_keys(self, limit=None):
        cmd = "services api-keys list --sort-by=~createTime"
        if limit:
            cmd += f"--limit={limit}"
        keys = self.GCP.exec(cmd)
        return keys
    def create_key(self, keyName, apiTargets=None, allowedIps=None):
        cmd = f"services api-keys create --display-name='{keyName}' "
        flags = []
        if apiTargets:
            flags += [f"--api-target='{target}'" for target in apiTargets]
        if allowedIps:
            flags.append(f"--allowed-ips='{allowedIps}'")
        cmd += ' '.join(flags)
        print(cmd)
        keyId = self.GCP.exec(cmd).get('response').get('uid')
        return keyId    
    def delete_key(self, keyId):
        self.GCP.exec(f"services api-keys delete {keyId}")
    def get_key_string(self, keyId):
        keyString = self.GCP.exec(f"services api-keys get-key-string {keyId}").get('keyString')
        return keyString
    def get_key_config(self, keyId):
        keyConfig = self.GCP.exec(f"services api-keys describe {keyId}")
        return keyConfig
    def rotate_key(self, oldKeyId):
        keyInfo = self.get_key_config(oldKeyId)
        name = keyInfo.get('displayName')
        restrictions = keyInfo.get('restrictions', {})
        targets = restrictions.get('apiTargets', None)
        ips = restrictions.get('serverKeyRestrictions', {}).get('allowedIps', None)
        apiTargets = [f"{key}={value}" for target in targets for key, value in target.items()] if targets else None
        allowedIps = ",".join(ips) if ips else None
        newKeyId = self.create_key(name, apiTargets, allowedIps)
        newKeyString = self.get_key_string(newKeyId)
        return newKeyId, newKeyString




def checkSecrets(sMan, expiryTime):
    keyIds = []
    secrets = sMan.list_secrets()
    for secret in secrets:
        latestVersion = sMan.latest_version(secret)
        createDate = datetime.strptime(latestVersion.get('createTime'), '%Y-%m-%dT%H:%M:%S.%fZ')
        if datetime.now(datetime.timezone.utc) - createDate > timedelta(days=expiryTime):
            latestAnnotation = sMan.latest_annotation(secret)
            keyIds.append(next(iter(latestAnnotation.values())))
    return keyIds

def rotateKeys(kMan, oldKeyIds):
    newKeys = []
    for oldKeyId in oldKeyIds:
        newKeyId, newKeyString = kMan.rotate_key(oldKeyId)
        newKeys.append({newKeyId: newKeyString})
    return newKeys

def updateSecrets(sMan, keys):
    return 0

"""
def main(projectID):
    kMan = KeyManager(projectID)
    sMan = SecretManager(projectID, kMan)

if __name__ == "__main__":
    main(projectID)
#"""