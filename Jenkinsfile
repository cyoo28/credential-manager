// Flag for if changes have been made to source code
def changesFound = false

pipeline {
    agent any

    environment {
        // Source Code
        CODE = 'api_key_rotation.py'
        // ECR repository details
        ECR_REGISTRY = '026090555438.dkr.ecr.us-east-1.amazonaws.com'
        ECR_REPO = 'credential-manager/key-rotation'
        DOCKER_IMAGE = "${ECR_REGISTRY}/${ECR_REPO}"
        DOCKER_TAG = 'latest'
        // ECS cluster and task details
        REGION = 'us-east-1'
        CLUSTER_NAME = 'gcpKeyRotation-cluster'
        TASK_DEFINITION = 'gcpKeyRotation-task:1'
        SUBNET = 'subnet-020c7a0407b1103ba'
        SECURITY_GROUP = 'sg-03e632351b9ecb3e0'
        ECS_CONTAINER = 'gcpKeyRotation-container'
    }

    stages {
        stage('Checkout') {
            steps {
                // Check out the code from the repository
                git branch: 'main', url: 'https://github.com/cyoo28/credential-manager.git'
            }
        }

        stage('Detect Changes') {
            steps {
                script {
                    def changes = sh(
                        // Check if there have been any changes made to source code
                        script: 'git diff --name-only HEAD~1 HEAD | grep "^${CODE}\$" || true',
                        returnStdout: true
                    ).trim()
                    // set flag if there are changes
                    if (changes) {
                        echo "Changes detected in ${CODE}"
                        changesFound = true
                    // otherwise skip the pipeline
                    } else {
                        echo "No changes in ${CODE}. Skipping pipeline."
                        currentBuild.result = 'SUCCESS'
                        return 
                    }
                }
            }
        }

        stage('Build Docker Image') {
            when {
                expression { return changesFound }
            }
            steps {
                script {
                    // Build the Docker image using the Dockerfile in the repo
                    docker.build("${DOCKER_IMAGE}:${DOCKER_TAG}")
                }
            }
        }
        
        stage('Test Docker Image') {
            when {
                expression { return changesFound }
            }
            steps {
                script {
                    // Run the Docker image
                    sh '''
                        docker run --rm ${DOCKER_IMAGE}:${DOCKER_TAG} ix-sandbox 0 --secretName ix-gcp-service-account --sender notify@ixcloudsecurity.com --recipients cyoo@ixcloudsecurity.com --test
                    '''
                }
            }
        }

        stage('Login to AWS ECR') {
            when {
                expression { return changesFound }
            }
            steps {
                script {
                    // Log in to AWS ECR using the AWS CLI and IAM role credentials
                    sh '''
                        aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${ECR_REGISTRY}
                    '''
                }
            }
        }

        stage('Push Docker Image to ECR') {
            when {
                expression { return changesFound }
            }
            steps {
                script {
                    // Tag the image with the ECR registry URL
                    sh '''
                        docker tag ${DOCKER_IMAGE}:${DOCKER_TAG} ${ECR_REGISTRY}/${ECR_REPO}:${DOCKER_TAG}
                    '''
                    // Push the image to ECR
                    sh '''
                        docker push ${ECR_REGISTRY}/${ECR_REPO}:${DOCKER_TAG}
                    '''
                }
            }
        }

        stage('Scan Image for Vulnerabilities') {
            when {
                expression { return changesFound }
            }
            steps {
                script {
                    // Run the scan
                    sh """
                        aws ecr start-image-scan \
                        --repository-name ${ECR_REPO} \
                        --image-id imageTag=${DOCKER_TAG} \
                        --region ${REGION}
                    """
                    // Wait a few seconds for the scan to complete
                    sleep 10
                    // Fetch findings
                    def findings = sh(
                        script: """
                            aws ecr describe-image-scan-findings \
                            --repository-name ${ECR_REPO} \
                            --image-id imageTag=${DOCKER_TAG} \
                            --region ${REGION} \
                            --output json
                        """,
                        returnStdout: true
                    ).trim()
                    echo "Scan findings:\n${findings}"
                    // Parse only CRITICAL findings
                    def criticalFindings = sh(
                        script: """
                            aws ecr describe-image-scan-findings \
                            --repository-name ${ECR_REPO} \
                            --image-id imageTag=${DOCKER_TAG} \
                            --region ${REGION} \
                            --query "imageScanFindings.findings[?severity=='CRITICAL']" \
                            --output json
                        """,
                        returnStdout: true
                    ).trim()
                    // Fail the pipeline if there are critical vulnerabilities
                    if (criticalFindings != "[]") {
                        error("CRITICAL vulnerabilities found! Failing the build.")
                    // otherwise the image is fine
                    } else {
                        echo "No critical vulnerabilities found."
                    }
                }
            }
        }

        stage('Test Docker Image as ECS Task') {
            when {
                expression { return changesFound }
            }
            steps {
                script {
                    // run the image as an ecs task
                    sh """
                    aws ecs run-task \
                      --region ${REGION} \
                      --cluster ${CLUSTER_NAME} \
                      --launch-type FARGATE \
                      --task-definition ${TASK_DEFINITION} \
                      --network-configuration 'awsvpcConfiguration={subnets=["${SUBNET}"],securityGroups=["${SECURITY_GROUP}"],assignPublicIp="ENABLED"}' \
                      --overrides '{
                        "containerOverrides": [{
                          "name": "${ECS_CONTAINER}",
                          "command": ["ix-sandbox", "0", "--secretName", "ix-gcp-service-account", "--sender", "notify@ixcloudsecurity.com", "--recipients", "alert@ixcloudsecurity.com", "--test"]
                        }]
                      }'
                    """
                }
            }
        }
    }

    post {
        success {
            echo 'Pipeline executed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check the logs for details.'
        }
    }
}
