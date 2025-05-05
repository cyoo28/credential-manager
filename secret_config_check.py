#!/usr/bin/env python3
import sys
import os
import json
from datetime import datetime, timezone, timedelta
import argparse
from api_key_rotation import SecretManager, KeyManager

# Arg:
#   projectId [str] - name of GCP project
#   fileName [str] *opt - name of the output file (default=secrets-rotation.csv)
def main(projectId, fileName="secrets-config.csv"):
    # Initialize the key and secret manager instances
    kMan = KeyManager(projectId, debug=False, test=False)
    sMan = SecretManager(projectId, kMan, debug=False, test=False)
    # Begin the file and write the headers
    with open(fileName, "w") as file:
        file.write("Secret Name, Status, Is Latest Enabled?, How Many Versions Enabled?, Which Versions Enabled?, Error\n")
    # List all the secrets
    secrets = sMan.list_secrets()
    # There might not be any secrets in the project
    if not secrets:
        print("Error: There are no secrets in this project")
    for secret in secrets:
        secretName = secret.get("name").split("/")[-1]
        print(f"-----\nSecret Name: {secretName}")
        secretType = sMan.check_type(secretName)
        # Check that the secret is for an api key
        if not secretType=="api_key":
            print(f"{secretName} is not an api_key")
            continue
        # List the versions for the secret
        versions = sMan.list_versions(secretName)
        # The secret might not have any versions
        if not versions:
            print(f"Error: {secretName} has no versions")
            with open(fileName, "a") as file:
                file.write(f"{secretName}, INSUFFICIENT DATA, -, -, -, No versions\n")
            continue
        # Check the enabled versions
        enabledVersions = []
        for version in versions:
            if version.get('state') == 'ENABLED':
                enabledVersions.append(version.get('name').split("/")[-1])
        totalEnabled = len(enabledVersions)
        enabledVersions = "/".join(enabledVersions)
        # Check if the latest version is enabled
        latestVersion = sMan.latest_version(secretName, enabled=False)
        latestEnabled = latestVersion.get('state')=='ENABLED'
        print(f"{secretName}:\n  is latest enabled: {latestEnabled}\n  total versions enabled: {totalEnabled}")
        # Write results to output file
        with open(fileName, "a") as file:
            file.write(f"{secretName}")
        # If latest is the only version enabled
        if latestEnabled and totalEnabled <= 1:
            with open(fileName, "a") as file:
                file.write(", OK")
                error = "-"
        # Otherwise, it's in violation
        else:
            with open(fileName, "a") as file:
                file.write(", IN VIOLATION")
            if not latestVersion:
                error = 'Latest version not enabled'
            elif totalEnabled > 1:
                error = 'Multiple versions enabled'
        with open(fileName, "a") as file:
            file.write(f", {latestEnabled}, {totalEnabled}, {enabledVersions}, {error}\n")

if __name__ == "__main__":
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description="Use this script to rotate keys associated with old secrets")
    # Create arguments
    parser.add_argument("projectId", type=str, help="Google Cloud Project Id")
    parser.add_argument("--fileName", dest="fileName", type=str, default="secrets-config.csv", help="Name of your file (\"secrets-config.csv\" if not specified)")
    # Parse the command-line arguments
    args = parser.parse_args(sys.argv[1:])
    projectId = args.projectId
    fileName = args.fileName
    # Pass arguments to the main function
    main(projectId, fileName)
