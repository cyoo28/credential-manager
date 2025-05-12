pipeline {
    agent any

    environment {
        // ECR repository details
        ECR_REGISTRY = '026090555438.dkr.ecr.us-east-1.amazonaws.com'
        ECR_REPO_NAME = 'credential-manager/key-rotation'
        DOCKER_IMAGE_NAME = "${ECR_REGISTRY}/${ECR_REPO_NAME}"
        DOCKER_TAG = 'latest'
    }

    stages {
        stage('Checkout') {
            steps {
                // Check out the code from the repository
                git branch: 'main', url: 'https://github.com/cyoo28/credential-manager.git'
                //git 'https://github.com/cyoo28/credential-manager.git'
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    // Build the Docker image using the Dockerfile in the repo
                    docker.build("${DOCKER_IMAGE_NAME}:${DOCKER_TAG}")
                }
            }
        }

        stage('Login to AWS ECR') {
            steps {
                script {
                    // Log in to AWS ECR using the AWS CLI and IAM role credentials
                    sh '''
                        $(aws ecr get-login --no-include-email --region us-east-1)
                    '''  // Replace "region" with your AWS region (e.g., us-east-1)
                }
            }
        }

        stage('Push Docker Image to ECR') {
            steps {
                script {
                    // Tag the image with the ECR registry URL
                    sh '''
                        docker tag ${DOCKER_IMAGE_NAME}:${DOCKER_TAG} ${ECR_REGISTRY}/${ECR_REPO_NAME}:${DOCKER_TAG}
                    '''
                    // Push the image to ECR
                    sh '''
                        docker push ${ECR_REGISTRY}/${ECR_REPO_NAME}:${DOCKER_TAG}
                    '''
                }
            }
        }
    }

    post {
        success {
            echo 'Docker image built and pushed to AWS ECR successfully!'
        }
        failure {
            echo 'Build failed. Check the logs for details.'
        }
    }
}
