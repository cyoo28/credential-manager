pipeline {
    agent any

    environment {
        // ECR repository details
        ECR_REGISTRY = '026090555438.dkr.ecr.us-east-1.amazonaws.com'
        ECR_REPO_NAME = 'credential-manager/key-rotation'
        DOCKER_IMAGE_NAME = "${ECR_REGISTRY}/${ECR_REPO_NAME}"
        DOCKER_TAG = 'latest'
        CHANGES_FOUND = false
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
                        env.CHANGES_FOUND = true
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
                expression { env.CHANGES_FOUND == true }
            }
            steps {
                script {
                    // Build the Docker image using the Dockerfile in the repo
                    docker.build("${DOCKER_IMAGE_NAME}:${DOCKER_TAG}")
                }
            }
        }
        
        stage('Test Docker Image') {
            when {
                expression { env.CHANGES_FOUND == true }
            }
            steps {
                script {
                    // Run the Docker image
                    sh '''
                        docker run --rm ${DOCKER_IMAGE_NAME}:${DOCKER_TAG} ix-sandbox 0 --secretName ix-gcp-service-account --sender notify@ixcloudsecurity.com --recipients cyoo@ixcloudsecurity.com --test
                    '''
                }
            }
        }

        stage('Login to AWS ECR') {
            when {
                expression { env.CHANGES_FOUND == true }
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
                expression { env.CHANGES_FOUND == true }
            }
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
