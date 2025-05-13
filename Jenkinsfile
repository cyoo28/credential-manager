// Flag for if changes have been made to api_key_rotation.py
def changesFound = false

pipeline {
    agent any

    environment {
        // ECR repository details
        ECR_REGISTRY = '026090555438.dkr.ecr.us-east-1.amazonaws.com'
        ECR_REPO = 'credential-manager/key-rotation'
        DOCKER_IMAGE = "${ECR_REGISTRY}/${ECR_REPO}"
        DOCKER_TAG = 'latest'
        // ECS cluster and task details
        AWS_REGION = 'us-east-1'
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
                //git 'https://github.com/cyoo28/credential-manager.git'
            }
        }

        stage('Detect Changes') {
            steps {
                script {
                    def changes = sh(
                        script: 'git diff --name-only HEAD~1 HEAD | grep "^api_key_rotation.py\$" || true',
                        returnStdout: true
                    ).trim()
                    // Check if there have been any changes made to api_key_rotation.py
                    if (changes) {
                        echo "Changes detected in api_key_rotation.py"
                        changesFound = true
                    } else {
                        echo "No changes in api_key_rotation.py. Skipping pipeline."
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

        stage('Test Docker Image as ECS Task') {
            when {
                expression { return changesFound }
            }
            steps {
                script {
                    sh """
                    aws ecs run-task \
                      --region ${AWS_REGION} \
                      --cluster ${CLUSTER_NAME} \
                      --launch-type FARGATE \
                      --task-definition ${TASK_DEFINITION} \
                      --network-configuration 'awsvpcConfiguration={subnets=["${SUBNET}"],securityGroups=["${SECURITY_GROUP}"],assignPublicIp="ENABLED"}' \
                      --overrides '{
                        "containerOverrides": [{
                          "name": "${ECS_CONTAINER}",
                          "command": [ix-sandbox, 0, --sender, notify@ixcloudsecurity.com, --recipients, alert@ixcloudsecurity.com, --test]
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
