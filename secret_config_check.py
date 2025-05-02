#!/usr/bin/env python3
import sys
import os
import json
from datetime import datetime, timezone, timedelta
import argparse
from api_key_rotation import SecretManager, KeyManager

def main(projectId, fileName="secrets-config.csv", debug=False, test=False):
    kMan = KeyManager(projectId, debug, test)
    sMan = SecretManager(projectId, kMan, debug, test)
    with open(fileName, "w") as file:
        file.write("Secret Name, Status, Latest Version Enabled, Versions Enabled, Error\n")
    secrets = sMan.list_secrets()
    if not secrets:
        print("Error: There are no secrets in this project")
    for secret in secrets:
        secretName = secret.get("name").split("/")[-1]
        versions = sMan.list_versions(secretName)
        if not versions:
            print(f"Error: {secretName} has no versions")
            with open(fileName, "a") as file:
                file.write(f"{secretName}, INSUFFICIENT DATA, -, -, No versions\n")
            continue
        totalEnabled = sum(1 for version in versions if version.get('state') == 'ENABLED')
        latestVersion = sMan.latest_version(secretName, enabled=False)
        latestEnabled = latestVersion.get('state')=='ENABLED'
        print(f"{secretName}:\n  is latest enabled: {latestEnabled}\n  total versions enabled: {totalEnabled}")
        with open(fileName, "a") as file:
            file.write(f"{secretName}")
        if latestEnabled and totalEnabled <= 1:
            with open(fileName, "a") as file:
                file.write(", OK")
        else:
            with open(fileName, "a") as file:
                file.write(", IN VIOLATION")     
        with open(fileName, "a") as file:
            file.write(f", {latestEnabled}, {totalEnabled}, -\n")

if __name__ == "__main__":
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description="Use this script to rotate keys associated with old secrets")
    # Create arguments
    parser.add_argument("projectId", type=str, help="Google Cloud Project Id")
    parser.add_argument("--fileName", dest="fileName", type=str, default="secrets-config.csv", help="Name of your file (\"secrets-config.csv\" if not specified)")
    parser.add_argument("--debug", dest="debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--test", dest="test", action="store_true", help="Enable dry-run testing mode")
    # Parse the command-line arguments
    args = parser.parse_args(sys.argv[1:])
    projectId = args.projectId
    fileName = args.fileName
    debug = args.debug
    test = args.test
    # Pass arguments to the main function
    main(projectId, fileName, debug, test)
