import os
import json

class GCP:
    def __init__(self, projectID):
        self.projectID = projectID
    def exec(self, command, format="json"):
        response = os.popen("gcloud {} --format={} --project={}".format(command, format, self.projectID))
        return json.loads(response.read())
    def custom_exec(self, command):
        response = os.popen(command)
        return json.loads(response.read())
        
class SecretManager:
    def __init__(self, projectID):
        self.projectID = projectID
        self.GCP = GCP(self.projectID)
        self.KeyGen = KeyManager(self.projectID, self.GCP)
    def list_secrets(self):
        secrets = self.GCP.exec("secrets list", "json")
        return secrets
    def describe_secret(self, secretName):
        secret = self.GCP.exec("secrets describe {}".format(secretName), "json")
        return secret
    def list_versions(self, secretName):
        versions = self.GCP.exec("secrets versions list {}".format(secretName, "json"))
        return versions
    def disable_version(self, version, secretName):
        self.GCP.write_exec("secrets versions disable {} --secret={}".format(version, secretName))
    def add_version(self, keyName, secretValue, secretName):
        self.GCP.custom_exec("echo -n {} | gcloud secrets versions add {} --data-file=- --project={}".format(secretValue, secretName, self.projectID))
        version = self.GCP.exec("secrets versions list {} --limit=1 --sort-by=~createTime".format(secretName), "value(name)")
        annotation = "version_{}={}".format(version, keyName.replace(" ","_"))
        self.GCP.write_exec("secrets update {} --update-annotations={}".format(secretName, annotation))
        # should i save key name or ID in annotation? leaning towards ID
class KeyManager:
    def __init__(self, projectID, GCP):
        self.projectID = projectID
        self.GCP = GCP
    def list_keys(self):
        keys = self.GCP.exec("services api-keys list")
        return keys
    def delete_key(self, keyID):
        self.GCP.exec("services api-keys delete {}".format(keyID))
    
    # how to clone a key?
    def get_key_config(self, keyID):
        self.keyConfig = self.GCP.exec("services api-keys describe {}".format(keyID))
        return self.keyConfig
    # How to get Key ID when creating a key
    def create_key(self, keyName):
        self.GCP.exec("services api-keys create --display-name={}".format(keyName))
    def update_key(self, keyName):
        self.GCP.exec("services api-keys update --display-name={} --restrictions={}".format(keyName, json.dumps(self.keyConfig)))
    

def main():
    test