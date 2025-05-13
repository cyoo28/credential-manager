#!/usr/bin/env python3
import sys
import os
import json
from datetime import datetime, timezone, timedelta
import argparse
from api_key_rotation import SecretManager, KeyManager

# Arg:
#   projectId [str] - name of GCP project
#   keyId [str] - the key uid to search for
def main(projectId, keyId):
    # Initialize the key and secret manager instances
    kMan = KeyManager(projectId, debug=False, test=False)
    sMan = SecretManager(projectId, kMan, debug=False, test=False)
    # Get list of all secrets
    secrets = sMan.list_secrets()
    # Search for secret that has annotation matching the key Id
    secret = next((secret for secret in secrets if any(keyId == v for v in secret["annotations"].values())), None)
    # Report the secret name
    secretName = secret.get("name").split("/")[-1]
    print(f"Key uid: {keyId}\n Secret: {secretName}")
    
if __name__ == "__main__":
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(description="Use this script to rotate keys associated with old secrets")
    # Create arguments
    parser.add_argument("projectId", type=str, help="Google Cloud Project Id")
    parser.add_argument("keyId", type=str, help="The key uid that you would like to search with")
    # Parse the command-line arguments
    args = parser.parse_args(sys.argv[1:])
    projectId = args.projectId
    keyId = args.keyId
    # Pass arguments to the main function
    main(projectId, keyId)