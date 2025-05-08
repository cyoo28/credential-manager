# GCP Credential Manager
This project automates GCP api key rotation. This project was completed in May 2025.

## Table of Contents
* [What was the problem?](#what-was-the-problem?)
* [What was the solution?](#what-was-the-solution?)

## What was the problem?
Like most platforms, Google Cloud Platform (GCP) offers API keys to allow for programmatic access. However, when it comes to GCP, there are 2 main issues with API keys. The first issues is that they do not identify the principal using the key. As a result, there is no way of checking whether the caller is actually authorized to perform the requested operations with the key. The second issue is that the usage is not logged in audit logs. Additionally, API keys are prone to cut/paste usage, leading to high risk of unauthorized exposure. Therefore, it is important to find a solution that remedies these issues and mitigates the risk of key exposure.

## What was the solution?
One solution for this problem, is to utilize GCP Secret Manager. Instead of directly accessing API keys, principals will have to access the corresponding secret. This way, the principal using the secret (and hence the key) can now be monitored and the secret's usage can now be logged in audit logs. However, one issue that this solution presents is that GCP does not currently have a function to automatically rotate API keys and propagate these changes to the corresponding secret. Therefore, api_key_rotation.py has been created to look through Secret Manager and rotate any keys that are older than the desired timeframe. This solution uses annotations to determine which secrets are used for API keys and to associate secret versions with their corresponding key. The gcloud library that this script uses does not currently have a command to rotate an existing key. Instead, when a secret version is older than the desired time, a new key is created, the display name and configuration of the old key is copied to the new key, and the old key is deleted. The new key string is then stored as a new secret version and a new annotation is created associating the version with the new key's uid.

In order to best manage these API key secrets, the latest version of each secret should correspond to the latest key. Older versions of the secret should be disabled and outdated keys should be deleted. api_key_rotation.py assumes that the latest version of a secret is the only enabled version for each secret. To verify that this is the case, secret_config_check.py can be run to check API key secrets and identify any secrets that have more than one version enabled or that do not have the latest version enabled. Secrets that are in violation will be reported so that they can be properly configured. The code for this project uses the following packages:

 ### Code Packages
 * Python 3.11.2
  * boto3 1.36.1
 * gcloud 521.0.0

The code has also been containerized using Docker and can be run using either AWS Lambda or Elastic Container Service (ECS). To access the secrets and API keys in GCP, credentials for a GCP service account are stored in AWS Secrets Manager. This secret is accessed by Lambda or ECS to authenticate and authorize use of gcloud (which allows CLI access to GCP services/resources). The solution is run once a day using an EventBridge scheduler and uses Simple Email Service to alert the SecOps team of secrets that have been changed. This information includes:
* The secret name
* The old secret version
* The new secret version
* The key display name
* The old key uid
* The new key uid

### AWS Services
* IAM
* Secrets Manager
* ECS (or Lambda)
* SES
* EventBridge

### GCP Services
* Secret Manager
* APIs & Services
