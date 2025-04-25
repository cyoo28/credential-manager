import os
import json

class GCP:
    def __init__(self, projectID):
        self.projectID = projectID
    def exec(self, command, format="json"):
        cmd = "gcloud {} --format='{}' --project={}".format(command, format, self.projectID)
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
    def __init__(self, projectID, credManager):
        self.projectID = projectID
        self.GCP = GCP(self.projectID)
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
            versions = self.GCP.exec("secrets versions list {} --sort-by=~createTime".format(secretName), "json(name)")[0]
        else:
            versions = self.GCP.exec("secrets versions list {} --limit={} --sort-by=~createTime".format(secretName, limit), "json(name)")[0]
        return [value.split("/")[-1] for value in versions.values()]
    def list_latest_version(self, secretName):
        latestVersion = self.list_versions(secretName, 1)[0]
        return latestVersion
    def list_annotations(self, secretName):
        secretDetails = self.describe_secret(secretName)
        annotations = secretDetails['annotations']
        return annotations
    def list_latest_annotation(self, secretName):
        latestVersion = self.list_latest_version(secretName)
        annotations = self.list_annotations(secretName)
        latestAnnotation = annotations["version_{}".format(latestVersion)]
        return latestAnnotation
    def enable_version(self, version, secretName):
        self.GCP.exec("secrets versions enable {} --secret={}".format(version, secretName))
    def disable_version(self, version, secretName):
        self.GCP.exec("secrets versions disable {} --secret={}".format(version, secretName))
    def add_annotation(self, keyID, version, secretName):
        annotations = self.list_annotations(secretName)
        annotations["version_{}".format(version)] = keyID
        self.GCP.exec("secrets update {} --update-annotations='{}'".format(secretName, ",".join([key+"="+value for key, value in annotations.items()])))
    def add_version(self, keyID, secretValue, secretName):
        versionDetails = self.GCP.custom_exec("echo -n {} | gcloud secrets versions add {} --data-file=- --project={} --format=json".format(secretValue, secretName, self.projectID))
        version = versionDetails["name"].split("/")[-1]
        self.add_annotation(keyID, version, secretName)
        

class KeyManager:
    def __init__(self, projectID):
        self.projectID = projectID
        self.GCP = GCP(self.projectID)
    def list_keys(self, limit=None):
        if not limit:
            keys = self.GCP.exec("services api-keys list --sort-by=~createTime")
        else:
            keys = self.GCP.exec("services api-keys list --limit={} --sort-by=~createTime".format(limit))
        return keys
    def delete_key(self, keyID):
        self.GCP.exec("services api-keys delete {}".format(keyID))
    def create_key(self, keyName):
        response = self.GCP.exec("services api-keys create --display-name='{}'".format(keyName))
        keyID = response['response']['uid']
        return keyID

    # how to clone a key?
    def get_key_config(self, keyID):
        self.keyConfig = self.GCP.exec("services api-keys describe {}".format(keyID))
        return self.keyConfig
    
    def update_key(self, keyName):
        self.GCP.exec("services api-keys update --display-name={} --restrictions={}".format(keyName, json.dumps(self.keyConfig)))
    

def main():
    test